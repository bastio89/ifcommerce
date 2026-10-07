from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import stripe
from fastapi.testclient import TestClient

from app.services.usage import StripeUsageReporter, UsageDetails, UsageMeter
from tests.conftest import Db


class FakeMeterEvents:
    def __init__(self, fail_for: set[str] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._fail_for = fail_for or set()

    async def create_async(self, params: dict[str, Any]) -> None:
        if params["identifier"] in self._fail_for:
            raise stripe.APIConnectionError("network down")
        self.calls.append(params)


class FakeConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchval(self, query: str, *args: Any) -> str:
        self.calls.append((query, args))
        return "usage-id"


def test_usage_can_be_recorded_inside_job_transaction() -> None:
    connection = FakeConnection()
    meter = UsageMeter(None)  # type: ignore[arg-type]

    usage_id = asyncio.run(
        meter.record(
            tenant_id="tenant-id",
            api_key_id="key-id",
            operation_type="ANALYZE_TICKET",
            billable=True,
            details=UsageDetails(category="PRODUCT_ISSUE", urgency=3, engine="heuristic-v1", latency_ms=10),
            connection=connection,  # type: ignore[arg-type]
        )
    )

    assert usage_id == "usage-id"
    assert len(connection.calls) == 1
    query, args = connection.calls[0]
    assert "INSERT INTO usage_logs" in query
    assert args == ("tenant-id", "key-id", "ANALYZE_TICKET", "PRODUCT_ISSUE", 3, "heuristic-v1", 10, True)


def _reporter(client: TestClient, events: FakeMeterEvents) -> StripeUsageReporter:
    fake_stripe = SimpleNamespace(v1=SimpleNamespace(billing=SimpleNamespace(meter_events=events)))
    return StripeUsageReporter(
        client.app.state.container.pool,  # type: ignore[attr-defined]
        fake_stripe,  # type: ignore[arg-type]
        event_name="decidecommerce_ticket_analyzed",
        interval_seconds=60,
    )


def _insert_usage(db: Db, tenant_id: str, *, billable: bool) -> str:
    return db.fetchval(
        """INSERT INTO usage_logs (tenant_id, operation_type, billable)
           VALUES ($1::uuid, 'ANALYZE_TICKET', $2) RETURNING id::text""",
        tenant_id,
        billable,
    )


def test_reports_only_billable_usage_once(client: TestClient, db: Db) -> None:
    db.execute("UPDATE usage_logs SET stripe_reported_at = now() WHERE stripe_reported_at IS NULL")
    tenant_id = db.create_tenant(plan="PRO", status="ACTIVE", customer="cus_meter")
    billable = [_insert_usage(db, tenant_id, billable=True) for _ in range(3)]
    _insert_usage(db, tenant_id, billable=False)

    events = FakeMeterEvents()
    reporter = _reporter(client, events)

    assert client.portal.call(reporter.flush) == 3  # type: ignore[union-attr]
    assert sorted(call["identifier"] for call in events.calls) == sorted(billable)
    assert {call["payload"]["stripe_customer_id"] for call in events.calls} == {"cus_meter"}
    assert all(call["event_name"] == "decidecommerce_ticket_analyzed" for call in events.calls)

    # Zweiter Lauf: nichts mehr offen.
    assert client.portal.call(reporter.flush) == 0  # type: ignore[union-attr]


def test_failed_events_are_retried_later(client: TestClient, db: Db) -> None:
    db.execute("UPDATE usage_logs SET stripe_reported_at = now() WHERE stripe_reported_at IS NULL")
    tenant_id = db.create_tenant(plan="PRO", status="ACTIVE", customer="cus_retry")
    ok_id = _insert_usage(db, tenant_id, billable=True)
    failing_id = _insert_usage(db, tenant_id, billable=True)

    first = FakeMeterEvents(fail_for={failing_id})
    assert client.portal.call(_reporter(client, first).flush) == 1  # type: ignore[union-attr]
    assert [call["identifier"] for call in first.calls] == [ok_id]

    second = FakeMeterEvents()
    assert client.portal.call(_reporter(client, second).flush) == 1  # type: ignore[union-attr]
    assert [call["identifier"] for call in second.calls] == [failing_id]
