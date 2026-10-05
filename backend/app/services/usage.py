"""Metering: schreibt UsageLog-Einträge und meldet abrechenbare Nutzung an Stripe."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import asyncpg
import stripe

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class UsageDetails:
    """Nicht-personenbezogene Metadaten einer Analyse (für Dashboard-Auswertungen)."""

    category: str | None = None
    urgency: int | None = None
    engine: str | None = None
    latency_ms: int | None = None


# Ein Roundtrip: Usage schreiben und last_used_at des Keys höchstens 1x/Minute aktualisieren.
_RECORD_SQL = """
WITH inserted AS (
    INSERT INTO usage_logs (tenant_id, api_key_id, operation_type, category, urgency, engine, latency_ms, billable)
    VALUES ($1::uuid, $2::uuid, $3::"OperationType", $4::"TicketCategory", $5, $6, $7, $8)
    RETURNING id
), touched AS (
    UPDATE api_keys SET last_used_at = now()
    WHERE id = $2::uuid AND (last_used_at IS NULL OR last_used_at < now() - interval '1 minute')
    RETURNING id
)
SELECT id::text FROM inserted
"""


class UsageMeter:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def record(
        self,
        *,
        tenant_id: str,
        api_key_id: str | None,
        operation_type: str,
        billable: bool,
        details: UsageDetails | None = None,
    ) -> str:
        details = details or UsageDetails()
        return await self._pool.fetchval(
            _RECORD_SQL,
            tenant_id,
            api_key_id,
            operation_type,
            details.category,
            details.urgency,
            details.engine,
            details.latency_ms,
            billable,
        )


_PENDING_SQL = """
SELECT u.id::text AS id, u."timestamp" AS ts, t.stripe_customer_id AS customer
FROM usage_logs u
JOIN tenants t ON t.id = u.tenant_id
WHERE u.billable
  AND u.stripe_reported_at IS NULL
  AND t.stripe_customer_id IS NOT NULL
  AND u."timestamp" > now() - interval '34 days'
ORDER BY u."timestamp"
LIMIT $1
"""
_MARK_REPORTED_SQL = "UPDATE usage_logs SET stripe_reported_at = now() WHERE id = ANY($1::uuid[])"
_REPORTER_LOCK_ID = 0x44434D45  # "DCME" – beliebige, projektweit eindeutige Advisory-Lock-ID


class StripeUsageReporter:
    """Hintergrund-Worker für Usage-Based Billing über Stripe Billing Meters.

    * Jede Analyse wird als Meter-Event mit ``identifier = usage_log.id`` gemeldet.
      Stripe dedupliziert anhand des Identifiers – Wiederholungen nach Abstürzen
      oder parallel laufende Backend-Replikas erzeugen keine Doppelabrechnung.
    * Inkludierte Volumina/Staffelpreise werden im Stripe-Preis konfiguriert,
      nicht im Code.
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        client: stripe.StripeClient,
        *,
        event_name: str,
        interval_seconds: float,
        batch_size: int = 200,
        concurrency: int = 8,
    ) -> None:
        self._pool = pool
        self._client = client
        self._event_name = event_name
        self._interval = interval_seconds
        self._batch_size = batch_size
        self._semaphore = asyncio.Semaphore(concurrency)
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="stripe-usage-reporter")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _run(self) -> None:
        while True:
            try:
                await self.flush()
            except Exception:
                logger.exception("Stripe usage reporting failed; will retry")
            await asyncio.sleep(self._interval)

    async def flush(self) -> int:
        async with self._pool.acquire() as conn, conn.transaction():
            # Nur ein Prozess (Worker/Replika) meldet gleichzeitig; die Sperre endet mit der Transaktion.
            if not await conn.fetchval("SELECT pg_try_advisory_xact_lock($1)", _REPORTER_LOCK_ID):
                return 0
            rows = await conn.fetch(_PENDING_SQL, self._batch_size)
            if not rows:
                return 0
            results = await asyncio.gather(*(self._report(row) for row in rows))
            reported = [row_id for row_id in results if row_id is not None]
            if reported:
                await conn.execute(_MARK_REPORTED_SQL, reported)
        logger.info("Reported %d/%d usage events to Stripe", len(reported), len(rows))
        return len(reported)

    async def _report(self, row: asyncpg.Record) -> str | None:
        timestamp: datetime = row["ts"]
        # Stripe akzeptiert keine Zeitstempel > 5 min in der Zukunft (Uhren-Drift absichern).
        timestamp = min(timestamp, datetime.now(UTC) + timedelta(minutes=4))
        async with self._semaphore:
            try:
                await self._client.v1.billing.meter_events.create_async(
                    {
                        "event_name": self._event_name,
                        "identifier": row["id"],
                        "timestamp": int(timestamp.timestamp()),
                        "payload": {"stripe_customer_id": row["customer"], "value": "1"},
                    }
                )
            except stripe.StripeError as exc:
                logger.warning("Meter event %s failed: %s", row["id"], exc)
                return None
        return row["id"]
