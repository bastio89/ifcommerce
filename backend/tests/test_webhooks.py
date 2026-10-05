from __future__ import annotations

import time

from fastapi.testclient import TestClient

from tests.conftest import Db, stripe_event, stripe_signature


def _subscription(customer: str, status: str, sub_id: str = "sub_123", tenant_id: str | None = None) -> dict:
    return {
        "id": sub_id,
        "object": "subscription",
        "customer": customer,
        "status": status,
        "metadata": {"tenant_id": tenant_id} if tenant_id else {},
        "items": {"object": "list", "data": [{"id": "si_1", "current_period_end": 1_900_000_000}]},
    }


def _post(client: TestClient, payload: bytes, signature: str | None = None):
    return client.post(
        "/api/v1/webhooks/stripe",
        content=payload,
        headers={"stripe-signature": signature or stripe_signature(payload), "content-type": "application/json"},
    )


def _tenant(db: Db, tenant_id: str):
    return db.fetchrow(
        "SELECT plan::text, subscription_status::text, stripe_subscription_id, "
        "subscription_current_period_end IS NOT NULL AS has_period FROM tenants WHERE id = $1::uuid",
        tenant_id,
    )


def test_rejects_invalid_signature(client: TestClient) -> None:
    payload = stripe_event("customer.subscription.created", _subscription("cus_x", "active"))
    response = _post(client, payload, signature="t=1,v1=deadbeef")
    assert response.status_code == 400


def test_subscription_lifecycle(client: TestClient, db: Db) -> None:
    tenant_id = db.create_tenant(customer="cus_lifecycle")

    created = stripe_event("customer.subscription.created", _subscription("cus_lifecycle", "active"))
    assert _post(client, created).json() == {"status": "processed"}
    assert dict(_tenant(db, tenant_id)) == {
        "plan": "PRO",
        "subscription_status": "ACTIVE",
        "stripe_subscription_id": "sub_123",
        "has_period": True,
    }

    # Stripe liefert Events mindestens einmal aus -> Duplikate werden erkannt.
    assert _post(client, created).json() == {"status": "duplicate"}

    unpaid = stripe_event("customer.subscription.updated", _subscription("cus_lifecycle", "unpaid"))
    _post(client, unpaid)
    assert _tenant(db, tenant_id)["subscription_status"] == "UNPAID"

    deleted = stripe_event("customer.subscription.deleted", _subscription("cus_lifecycle", "canceled"))
    _post(client, deleted)
    row = _tenant(db, tenant_id)
    assert (row["plan"], row["subscription_status"]) == ("FREE", "CANCELED")


def test_tenant_resolved_via_metadata(client: TestClient, db: Db) -> None:
    tenant_id = db.create_tenant()
    payload = stripe_event(
        "customer.subscription.created", _subscription("cus_new", "trialing", "sub_meta", tenant_id=tenant_id)
    )
    _post(client, payload)
    assert db.fetchval("SELECT stripe_customer_id FROM tenants WHERE id = $1::uuid", tenant_id) == "cus_new"
    assert _tenant(db, tenant_id)["subscription_status"] == "TRIALING"


def test_out_of_order_events_are_ignored(client: TestClient, db: Db) -> None:
    tenant_id = db.create_tenant(customer="cus_order")
    now = int(time.time())
    _post(
        client,
        stripe_event("customer.subscription.updated", _subscription("cus_order", "active", "sub_order"), created=now),
    )
    _post(
        client,
        stripe_event(
            "customer.subscription.updated", _subscription("cus_order", "incomplete", "sub_order"), created=now - 60
        ),
    )
    assert _tenant(db, tenant_id)["subscription_status"] == "ACTIVE"


def test_old_subscription_deletion_does_not_downgrade_new_one(client: TestClient, db: Db) -> None:
    tenant_id = db.create_tenant(customer="cus_switch")
    _post(client, stripe_event("customer.subscription.created", _subscription("cus_switch", "active", "sub_new")))
    _post(client, stripe_event("customer.subscription.deleted", _subscription("cus_switch", "canceled", "sub_old")))
    row = _tenant(db, tenant_id)
    assert (row["plan"], row["subscription_status"], row["stripe_subscription_id"]) == ("PRO", "ACTIVE", "sub_new")


def test_unrelated_events_are_acknowledged(client: TestClient) -> None:
    payload = stripe_event("invoice.paid", {"id": "in_1", "object": "invoice"})
    assert _post(client, payload).json() == {"status": "ignored"}
