"""Test-Infrastruktur.

Integrationstests laufen gegen eine echte PostgreSQL-Datenbank. Das Schema wird
aus den Prisma-Migrationen in /prisma/migrations erzeugt – exakt so wie in
Produktion. Ohne erreichbare Datenbank werden die Integrationstests übersprungen.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import string
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "prisma" / "migrations"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://decide:decide@localhost:5432/decidecommerce_test")
WEBHOOK_SECRET = "whsec_test_secret"
INTERNAL_SECRET = "internal-test-secret"
FREE_LIMIT = 3


def _admin_url(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    db_name = parts.path.lstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, "/postgres", "", "")), db_name


async def _recreate_database() -> None:
    admin_url, db_name = _admin_url(TEST_DATABASE_URL)
    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')
        await admin.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await admin.close()

    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        for migration in sorted(MIGRATIONS_DIR.glob("*/migration.sql")):
            await conn.execute(migration.read_text())
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def database() -> str:
    try:
        asyncio.run(_recreate_database())
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"PostgreSQL nicht erreichbar ({exc}); Integrationstests übersprungen.")
    return TEST_DATABASE_URL


@pytest.fixture()
def settings(database: str) -> Settings:
    return Settings(
        environment="test",
        database_url=database,
        decision_engine="heuristic",
        stripe_webhook_secret=WEBHOOK_SECRET,
        internal_api_secret=INTERNAL_SECRET,
        free_tier_monthly_limit=FREE_LIMIT,
        api_key_cache_ttl_seconds=0,
        db_pool_min_size=1,
        db_pool_max_size=4,
    )


@pytest.fixture()
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


class Db:
    """Synchroner Zugriff auf den App-Pool aus Tests heraus (läuft im App-Event-Loop)."""

    def __init__(self, client: TestClient) -> None:
        self._client = client
        self._pool: asyncpg.Pool = client.app.state.container.pool  # type: ignore[attr-defined]

    def _call(self, method: str, sql: str, *args: Any) -> Any:
        async def run() -> Any:
            return await getattr(self._pool, method)(sql, *args)

        return self._client.portal.call(run)  # type: ignore[union-attr]

    def fetchval(self, sql: str, *args: Any) -> Any:
        return self._call("fetchval", sql, *args)

    def fetchrow(self, sql: str, *args: Any) -> Any:
        return self._call("fetchrow", sql, *args)

    def fetch(self, sql: str, *args: Any) -> Any:
        return self._call("fetch", sql, *args)

    def execute(self, sql: str, *args: Any) -> Any:
        return self._call("execute", sql, *args)

    def create_tenant(self, *, plan: str = "FREE", status: str = "NONE", customer: str | None = None) -> str:
        return self.fetchval(
            """INSERT INTO tenants (name, plan, subscription_status, stripe_customer_id)
               VALUES ('Test Shop', $1::"Plan", $2::"SubscriptionStatus", $3) RETURNING id::text""",
            plan,
            status,
            customer,
        )

    def create_api_key(self, tenant_id: str, *, kind: str = "sk", origins: list[str] | None = None) -> tuple[str, str]:
        alphabet = string.ascii_letters + string.digits
        raw = f"dc_{kind}_" + "".join(secrets.choice(alphabet) for _ in range(40))
        key_id = self.fetchval(
            """INSERT INTO api_keys (tenant_id, name, type, key_hash, prefix, last4, allowed_origins)
               VALUES ($1::uuid, 'test', $2::"ApiKeyType", $3, $4, $5, $6) RETURNING id::text""",
            tenant_id,
            "PUBLISHABLE" if kind == "pk" else "SECRET",
            hashlib.sha256(raw.encode()).hexdigest(),
            raw[:10],
            raw[-4:],
            origins or [],
        )
        return raw, key_id


@pytest.fixture()
def db(client: TestClient) -> Db:
    return Db(client)


def stripe_signature(payload: bytes, secret: str = WEBHOOK_SECRET, timestamp: int | None = None) -> str:
    ts = timestamp or int(time.time())
    signed = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={signed}"


def stripe_event(event_type: str, subscription: dict[str, Any], *, created: int | None = None) -> bytes:
    event = {
        "id": f"evt_{secrets.token_hex(12)}",
        "object": "event",
        "type": event_type,
        "created": created or int(time.time()),
        "api_version": "2026-09-30.endive",
        "livemode": False,
        "data": {"object": subscription},
    }
    return json.dumps(event).encode()
