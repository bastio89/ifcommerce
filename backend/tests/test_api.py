"""End-to-End-Tests der API gegen echtes PostgreSQL (Schema aus den Prisma-Migrationen)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import FREE_LIMIT, INTERNAL_SECRET, Db

ANGRY_TICKET = {
    "text": (
        "Ich warte seit 3 Wochen auf meine Bestellung 4711-2025!!! Wenn das Paket nicht bis Freitag da ist, "
        "schalte ich meinen Anwalt ein. Max Mustermann, max@example.com"
    ),
    "external_id": "zendesk-123",
}


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok", "engine": "heuristic-v1"}
    assert client.get("/health/ready").json()["database"] == "up"


def test_missing_and_invalid_api_key(client: TestClient) -> None:
    response = client.post("/api/v1/analyze-ticket", json=ANGRY_TICKET)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_api_key"

    response = client.post("/api/v1/analyze-ticket", json=ANGRY_TICKET, headers={"x-api-key": "dc_sk_" + "x" * 40})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


def test_successful_analysis_is_metered(client: TestClient, db: Db) -> None:
    tenant_id = db.create_tenant()
    raw_key, key_id = db.create_api_key(tenant_id)

    response = client.post("/api/v1/analyze-ticket", json=ANGRY_TICKET, headers={"x-api-key": raw_key})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["category"] == "WHERE_IS_MY_ORDER"
    assert body["urgency"] == 5
    assert body["flags"] == {"is_cancellation_request": False, "contains_order_number": True}
    assert body["external_id"] == "zendesk-123"
    assert body["pii"] == {"redacted": True, "entities": {"EMAIL": 1, "NAME": 1}}
    assert "max@example.com" not in body["anonymized_text"]
    assert body["id"].startswith("ana_")

    log = db.fetchrow(
        "SELECT tenant_id::text, api_key_id::text, operation_type::text, category::text, urgency, billable "
        "FROM usage_logs WHERE tenant_id = $1::uuid",
        tenant_id,
    )
    assert dict(log) == {
        "tenant_id": tenant_id,
        "api_key_id": key_id,
        "operation_type": "ANALYZE_TICKET",
        "category": "WHERE_IS_MY_ORDER",
        "urgency": 5,
        "billable": False,
    }
    assert db.fetchval("SELECT last_used_at IS NOT NULL FROM api_keys WHERE id = $1::uuid", key_id)


def test_validation_errors_are_not_metered(client: TestClient, db: Db) -> None:
    tenant_id = db.create_tenant()
    raw_key, _ = db.create_api_key(tenant_id)

    response = client.post("/api/v1/analyze-ticket", json={"text": ""}, headers={"x-api-key": raw_key})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert db.fetchval("SELECT count(*) FROM usage_logs WHERE tenant_id = $1::uuid", tenant_id) == 0


def test_revoked_key_is_rejected(client: TestClient, db: Db) -> None:
    tenant_id = db.create_tenant()
    raw_key, key_id = db.create_api_key(tenant_id)
    db.execute("UPDATE api_keys SET revoked_at = now() WHERE id = $1::uuid", key_id)

    response = client.post("/api/v1/analyze-ticket", json=ANGRY_TICKET, headers={"x-api-key": raw_key})
    assert response.status_code == 401


def test_free_tier_quota(client: TestClient, db: Db) -> None:
    tenant_id = db.create_tenant()
    raw_key, _ = db.create_api_key(tenant_id)

    for _ in range(FREE_LIMIT):
        assert (
            client.post("/api/v1/analyze-ticket", json={"text": "Hallo?"}, headers={"x-api-key": raw_key}).status_code
            == 200
        )

    response = client.post("/api/v1/analyze-ticket", json={"text": "Hallo?"}, headers={"x-api-key": raw_key})
    assert response.status_code == 402
    assert response.json()["error"]["code"] == "monthly_quota_exceeded"


def test_pro_usage_is_billable_and_unlimited(client: TestClient, db: Db) -> None:
    tenant_id = db.create_tenant(plan="PRO", status="ACTIVE", customer="cus_pro")
    raw_key, _ = db.create_api_key(tenant_id)

    for _ in range(FREE_LIMIT + 2):
        assert (
            client.post("/api/v1/analyze-ticket", json={"text": "Hallo?"}, headers={"x-api-key": raw_key}).status_code
            == 200
        )
    assert db.fetchval("SELECT bool_and(billable) FROM usage_logs WHERE tenant_id = $1::uuid", tenant_id) is True


def test_unpaid_pro_subscription_is_locked(client: TestClient, db: Db) -> None:
    tenant_id = db.create_tenant(plan="PRO", status="UNPAID")
    raw_key, _ = db.create_api_key(tenant_id)

    response = client.post("/api/v1/analyze-ticket", json={"text": "Hallo?"}, headers={"x-api-key": raw_key})
    assert response.status_code == 402
    assert response.json()["error"]["code"] == "subscription_inactive"


def test_publishable_key_requires_allowed_origin(client: TestClient, db: Db) -> None:
    tenant_id = db.create_tenant()
    raw_key, _ = db.create_api_key(tenant_id, kind="pk", origins=["https://mein-shop.de"])

    denied = client.post(
        "/api/v1/analyze-ticket",
        json={"text": "Hallo?"},
        headers={"x-api-key": raw_key, "origin": "https://evil.example"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "origin_not_allowed"
    # CORS-Header auch auf Fehlern, damit das Widget die Antwort lesen kann.
    assert denied.headers["access-control-allow-origin"] == "*"

    allowed = client.post(
        "/api/v1/analyze-ticket",
        json={"text": "Hallo?"},
        headers={"x-api-key": raw_key, "origin": "https://mein-shop.de"},
    )
    assert allowed.status_code == 200


def test_cors_preflight_passes_without_api_key(client: TestClient) -> None:
    response = client.options(
        "/api/v1/analyze-ticket",
        headers={
            "origin": "https://mein-shop.de",
            "access-control-request-method": "POST",
            "access-control-request-headers": "x-api-key,content-type",
        },
    )
    assert response.status_code == 200
    assert "x-api-key" in response.headers["access-control-allow-headers"]


def test_text_length_limit(client: TestClient, db: Db) -> None:
    tenant_id = db.create_tenant()
    raw_key, _ = db.create_api_key(tenant_id)
    response = client.post("/api/v1/analyze-ticket", json={"text": "a" * 20_001}, headers={"x-api-key": raw_key})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_demo_endpoint_requires_internal_secret_and_is_not_metered(client: TestClient, db: Db) -> None:
    assert client.post("/api/v1/demo/analyze-ticket", json={"text": "Hallo"}).status_code == 403

    before = db.fetchval("SELECT count(*) FROM usage_logs")
    response = client.post(
        "/api/v1/demo/analyze-ticket",
        json={"text": "Mein Mixer ist kaputt."},
        headers={"x-internal-secret": INTERNAL_SECRET},
    )
    assert response.status_code == 200
    assert response.json()["category"] == "PRODUCT_ISSUE"
    assert db.fetchval("SELECT count(*) FROM usage_logs") == before


def test_wrong_method_is_405_not_500(client: TestClient, db: Db) -> None:
    tenant_id = db.create_tenant()
    raw_key, _ = db.create_api_key(tenant_id)
    response = client.get("/api/v1/analyze-ticket", headers={"x-api-key": raw_key})
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_session_timezone_survives_pool_reset(client: TestClient, db: Db) -> None:
    # asyncpg führt bei jeder Rückgabe RESET ALL aus; die Zeitzone muss trotzdem UTC bleiben.
    for _ in range(3):
        assert db.fetchval("SHOW timezone") == "UTC"
