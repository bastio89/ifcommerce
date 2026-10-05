"""Zugriffsregeln je Tarif und Subscription-Status."""

from __future__ import annotations

from dataclasses import dataclass

import asyncpg

from app.services.tenants import Plan, SubscriptionStatus, TenantContext

# Pro-Subscriptions mit vollem Zugriff (PAST_DUE = Kulanzzeitraum während Stripe-Retries).
_PRO_ACTIVE = {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING, SubscriptionStatus.PAST_DUE}
# Pro-Subscriptions, deren Zahlung endgültig ausblieb -> API gesperrt.
_PRO_LOCKED = {SubscriptionStatus.UNPAID, SubscriptionStatus.PAUSED}

_MONTHLY_USAGE_SQL = """
SELECT count(*) FROM usage_logs
WHERE tenant_id = $1::uuid
  AND "timestamp" >= date_trunc('month', now())
"""


@dataclass(frozen=True, slots=True)
class Entitlement:
    allowed: bool
    billable: bool
    error_code: str | None = None
    message: str | None = None
    status_code: int = 200


class EntitlementService:
    def __init__(self, pool: asyncpg.Pool, *, free_tier_monthly_limit: int) -> None:
        self._pool = pool
        self._free_limit = free_tier_monthly_limit

    async def check(self, tenant: TenantContext) -> Entitlement:
        if tenant.plan is Plan.PRO and tenant.subscription_status in _PRO_ACTIVE:
            return Entitlement(allowed=True, billable=True)

        if tenant.plan is Plan.PRO and tenant.subscription_status in _PRO_LOCKED:
            return Entitlement(
                allowed=False,
                billable=False,
                error_code="subscription_inactive",
                message="Die Pro-Subscription ist nicht bezahlt. Bitte Zahlungsdaten im Dashboard aktualisieren.",
                status_code=402,
            )

        # Free-Tarif (oder Pro, dessen Erstzahlung noch aussteht): Monatskontingent.
        used = await self._pool.fetchval(_MONTHLY_USAGE_SQL, tenant.tenant_id)
        if used >= self._free_limit:
            return Entitlement(
                allowed=False,
                billable=False,
                error_code="monthly_quota_exceeded",
                message=(
                    f"Das Free-Kontingent von {self._free_limit} Analysen pro Monat ist aufgebraucht. "
                    "Upgrade auf Pro für unbegrenzte, nutzungsbasierte Analysen."
                ),
                status_code=402,
            )
        return Entitlement(allowed=True, billable=False)
