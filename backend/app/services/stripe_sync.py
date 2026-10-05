"""Synchronisiert Stripe-Subscriptions in Echtzeit auf den Tenant (aktivieren / sperren / aktualisieren)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Any

import asyncpg

from app.services.tenants import Plan, SubscriptionStatus

logger = logging.getLogger(__name__)

SUBSCRIPTION_EVENTS = frozenset(
    {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }
)

# Subscriptions in diesen Zuständen sind beendet -> zurück auf Free.
_TERMINAL = {SubscriptionStatus.CANCELED, SubscriptionStatus.INCOMPLETE_EXPIRED}

SubscriptionFetcher = Callable[[str], Awaitable[Mapping[str, Any] | None]]


def _as_dict(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return dict(obj)


def map_status(stripe_status: str) -> SubscriptionStatus:
    try:
        return SubscriptionStatus(stripe_status.upper())
    except ValueError:
        logger.warning("Unknown Stripe subscription status %r, treating as UNPAID", stripe_status)
        return SubscriptionStatus.UNPAID


def _period_end(subscription: Mapping[str, Any]) -> datetime | None:
    # Seit API-Version 2025-03-31 liegt current_period_end auf den Subscription-Items.
    items = (subscription.get("items") or {}).get("data") or []
    candidates = [item.get("current_period_end") for item in items if item.get("current_period_end")]
    if not candidates and subscription.get("current_period_end"):
        candidates = [subscription["current_period_end"]]
    return datetime.fromtimestamp(max(candidates), tz=UTC) if candidates else None


def _customer_id(subscription: Mapping[str, Any]) -> str | None:
    customer = subscription.get("customer")
    if isinstance(customer, Mapping):
        return customer.get("id")
    return customer


class SubscriptionSyncService:
    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        fetch_subscription: SubscriptionFetcher | None = None,
        on_tenant_changed: Callable[[str], None] | None = None,
    ) -> None:
        self._pool = pool
        self._fetch_subscription = fetch_subscription
        self._on_tenant_changed = on_tenant_changed

    async def handle_event(self, event: Mapping[str, Any]) -> str:
        """Verarbeitet ein verifiziertes Stripe-Event genau einmal.

        Rückgabe: "processed", "duplicate" oder "ignored".
        """
        event_id: str = event["id"]
        event_type: str = event["type"]

        async with self._pool.acquire() as conn, conn.transaction():
            inserted = await conn.fetchval(
                "INSERT INTO stripe_events (id, type) VALUES ($1, $2) ON CONFLICT (id) DO NOTHING RETURNING id",
                event_id,
                event_type,
            )
            if inserted is None:
                return "duplicate"
            if event_type not in SUBSCRIPTION_EVENTS:
                return "ignored"

            payload = _as_dict(event["data"]["object"])
            subscription, authoritative = await self._latest_state(payload)
            tenant_id = await self._apply(
                conn,
                subscription,
                event_type=event_type,
                event_created=datetime.fromtimestamp(int(event["created"]), tz=UTC),
                authoritative=authoritative,
            )

        if tenant_id and self._on_tenant_changed:
            self._on_tenant_changed(tenant_id)
        return "processed"

    async def _latest_state(self, payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Holt den aktuellen Stand direkt von Stripe – macht die Verarbeitung reihenfolgeunabhängig."""
        if self._fetch_subscription is None:
            return payload, False
        try:
            fresh = await self._fetch_subscription(payload["id"])
        except Exception:
            logger.warning("Could not fetch subscription %s from Stripe, using event payload", payload["id"])
            return payload, False
        if fresh is None:
            return payload, False
        return _as_dict(fresh), True

    async def _apply(
        self,
        conn: asyncpg.Connection,
        subscription: Mapping[str, Any],
        *,
        event_type: str,
        event_created: datetime,
        authoritative: bool,
    ) -> str | None:
        subscription_id: str = subscription["id"]
        customer_id = _customer_id(subscription)
        metadata_tenant_id = (subscription.get("metadata") or {}).get("tenant_id")

        tenant = await conn.fetchrow(
            """
            SELECT id::text AS id, stripe_subscription_id, subscription_updated_at
            FROM tenants
            WHERE stripe_customer_id = $1 OR id::text = $2
            ORDER BY (stripe_customer_id = $1) DESC NULLS LAST
            LIMIT 1
            FOR UPDATE
            """,
            customer_id,
            metadata_tenant_id or "",
        )
        if tenant is None:
            logger.warning("No tenant for Stripe customer %s / subscription %s", customer_id, subscription_id)
            return None

        current_subscription = tenant["stripe_subscription_id"]
        if current_subscription and current_subscription != subscription_id:
            status = map_status(subscription.get("status", ""))
            if status in _TERMINAL or event_type == "customer.subscription.deleted":
                # Ein altes Abo endet, während bereits ein neues läuft -> ignorieren.
                logger.info("Ignoring %s for superseded subscription %s", event_type, subscription_id)
                return None

        if (
            not authoritative
            and tenant["subscription_updated_at"]
            and tenant["subscription_updated_at"] > event_created
        ):
            logger.info("Ignoring out-of-order event for subscription %s", subscription_id)
            return None

        status = map_status(subscription.get("status", ""))
        if event_type == "customer.subscription.deleted" and status not in _TERMINAL:
            status = SubscriptionStatus.CANCELED
        plan = Plan.FREE if status in _TERMINAL else Plan.PRO

        await conn.execute(
            """
            UPDATE tenants
            SET plan = $2::"Plan",
                subscription_status = $3::"SubscriptionStatus",
                stripe_subscription_id = $4,
                stripe_customer_id = COALESCE(stripe_customer_id, $5),
                subscription_current_period_end = $6,
                subscription_updated_at = GREATEST(COALESCE(subscription_updated_at, $7), $7),
                updated_at = now()
            WHERE id = $1::uuid
            """,
            tenant["id"],
            plan.value,
            status.value,
            subscription_id,
            customer_id,
            _period_end(subscription),
            event_created,
        )
        logger.info("Tenant %s -> plan=%s status=%s (%s)", tenant["id"], plan.value, status.value, event_type)
        return tenant["id"]
