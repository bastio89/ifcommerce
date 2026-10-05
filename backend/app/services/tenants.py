"""Auflösung API-Key -> Mandant, mit kurzem In-Process-Cache für den Hot Path."""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from enum import StrEnum

import asyncpg

from app.security import hash_api_key, looks_like_api_key


class Plan(StrEnum):
    FREE = "FREE"
    PRO = "PRO"


class SubscriptionStatus(StrEnum):
    NONE = "NONE"
    INCOMPLETE = "INCOMPLETE"
    INCOMPLETE_EXPIRED = "INCOMPLETE_EXPIRED"
    TRIALING = "TRIALING"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELED = "CANCELED"
    UNPAID = "UNPAID"
    PAUSED = "PAUSED"


class ApiKeyType(StrEnum):
    SECRET = "SECRET"  # noqa: S105 - Enum-Wert, kein Passwort
    PUBLISHABLE = "PUBLISHABLE"


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Alles, was der Request-Pfad über den Aufrufer wissen muss."""

    tenant_id: str
    tenant_name: str
    plan: Plan
    subscription_status: SubscriptionStatus
    stripe_customer_id: str | None
    api_key_id: str
    api_key_type: ApiKeyType
    allowed_origins: tuple[str, ...]


_RESOLVE_SQL = """
SELECT k.id::text            AS api_key_id,
       k.type::text          AS api_key_type,
       k.allowed_origins     AS allowed_origins,
       t.id::text            AS tenant_id,
       t.name                AS tenant_name,
       t.plan::text          AS plan,
       t.subscription_status::text AS subscription_status,
       t.stripe_customer_id  AS stripe_customer_id
FROM api_keys k
JOIN tenants t ON t.id = k.tenant_id
WHERE k.key_hash = $1
  AND k.revoked_at IS NULL
"""


class ApiKeyStore:
    """Validiert Schlüssel gegen PostgreSQL.

    Positive und negative Ergebnisse werden für ``ttl_seconds`` im Prozess
    gecacht (LRU, begrenzt). Ein Widerruf im Dashboard wirkt damit spätestens
    nach Ablauf der TTL – ein bewusster Trade-off zugunsten der Latenz.
    """

    def __init__(self, pool: asyncpg.Pool, *, ttl_seconds: float, max_entries: int = 10_000) -> None:
        self._pool = pool
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._cache: OrderedDict[str, tuple[float, TenantContext | None]] = OrderedDict()

    async def resolve(self, raw_key: str) -> TenantContext | None:
        if not looks_like_api_key(raw_key):
            return None
        key_hash = hash_api_key(raw_key)

        cached = self._cache.get(key_hash)
        now = time.monotonic()
        if cached is not None and cached[0] > now:
            self._cache.move_to_end(key_hash)
            return cached[1]

        row = await self._pool.fetchrow(_RESOLVE_SQL, key_hash)
        context = None
        if row is not None:
            context = TenantContext(
                tenant_id=row["tenant_id"],
                tenant_name=row["tenant_name"],
                plan=Plan(row["plan"]),
                subscription_status=SubscriptionStatus(row["subscription_status"]),
                stripe_customer_id=row["stripe_customer_id"],
                api_key_id=row["api_key_id"],
                api_key_type=ApiKeyType(row["api_key_type"]),
                allowed_origins=tuple(row["allowed_origins"] or ()),
            )

        self._cache[key_hash] = (now + self._ttl, context)
        self._cache.move_to_end(key_hash)
        while len(self._cache) > self._max_entries:
            self._cache.popitem(last=False)
        return context

    def invalidate_tenant(self, tenant_id: str) -> None:
        """Nach Stripe-Updates: Cache-Einträge des Mandanten verwerfen."""
        stale = [h for h, (_, ctx) in self._cache.items() if ctx is not None and ctx.tenant_id == tenant_id]
        for key_hash in stale:
            self._cache.pop(key_hash, None)
