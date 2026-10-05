"""ASGI-Middleware: API-Key-Validierung, Mandanten-Zuordnung, Kontingente und Metering.

Ablauf für geschützte Routen:

1. ``x-api-key`` gegen PostgreSQL validieren (mit kurzem Cache) -> TenantContext
2. Publishable Keys: Browser-Origin gegen die Allowlist des Keys prüfen
3. Rate-Limit pro Key (Token Bucket)
4. Tarif-/Subscription-Prüfung (Free-Kontingent, gesperrte Pro-Abos)
5. Request ausführen; bei Erfolg (2xx) einen UsageLog-Eintrag schreiben, BEVOR
   die Antwort den Client erreicht – jede ausgelieferte Analyse ist gemessen.

Als reine ASGI-Middleware (statt BaseHTTPMiddleware) blockiert sie kein
Streaming und fügt praktisch keinen Overhead hinzu.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.services.tenants import ApiKeyType, TenantContext
from app.services.usage import UsageDetails

if TYPE_CHECKING:
    from app.container import Container

logger = logging.getLogger(__name__)

# (Methode, Pfad) -> OperationType, das bei Erfolg gemessen wird.
METERED_ROUTES: dict[tuple[str, str], str] = {
    ("POST", "/api/v1/analyze-ticket"): "ANALYZE_TICKET",
}
PROTECTED_PATHS = frozenset(path for _, path in METERED_ROUTES)


async def _send_json(send: Send, status: int, code: str, message: str, headers: dict[str, str] | None = None) -> None:
    body = json.dumps({"error": {"code": code, "message": message}}).encode()
    raw_headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
    raw_headers += [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    await send({"type": "http.response.start", "status": status, "headers": raw_headers})
    await send({"type": "http.response.body", "body": body})


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key == name:
            return value.decode("latin-1")
    return None


class ApiKeyAuthMiddleware:
    def __init__(self, app: ASGIApp, container_getter: Callable[[Scope], Container]) -> None:
        self.app = app
        self._container_getter = container_getter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"].rstrip("/") not in PROTECTED_PATHS or scope["method"] == "OPTIONS":
            await self.app(scope, receive, send)
            return

        container = self._container_getter(scope)
        raw_key = _header(scope, b"x-api-key")
        if not raw_key:
            await _send_json(send, 401, "missing_api_key", "Header 'x-api-key' fehlt.")
            return

        tenant = await container.api_keys.resolve(raw_key.strip())
        if tenant is None:
            await _send_json(send, 401, "invalid_api_key", "API-Key ist ungültig oder wurde widerrufen.")
            return

        if tenant.api_key_type is ApiKeyType.PUBLISHABLE:
            origin = (_header(scope, b"origin") or "").rstrip("/")
            if not origin or origin not in tenant.allowed_origins:
                await _send_json(
                    send,
                    403,
                    "origin_not_allowed",
                    "Dieser Publishable Key ist für diese Domain nicht freigegeben.",
                )
                return

        per_minute = (
            container.settings.rate_limit_publishable_key_per_minute
            if tenant.api_key_type is ApiKeyType.PUBLISHABLE
            else container.settings.rate_limit_secret_key_per_minute
        )
        allowed, retry_after = container.rate_limiter.acquire(tenant.api_key_id, per_minute=per_minute)
        if not allowed:
            await _send_json(
                send,
                429,
                "rate_limited",
                "Zu viele Anfragen. Bitte später erneut versuchen.",
                {"retry-after": str(retry_after)},
            )
            return

        entitlement = await container.entitlements.check(tenant)
        if not entitlement.allowed:
            await _send_json(
                send, entitlement.status_code, entitlement.error_code or "forbidden", entitlement.message or ""
            )
            return

        state = scope.setdefault("state", {})
        state["tenant"] = tenant
        operation = METERED_ROUTES[(scope["method"], scope["path"].rstrip("/"))]

        async def metering_send(message: Message) -> None:
            if message["type"] == "http.response.start" and 200 <= message["status"] < 300:
                await self._record_usage(container, tenant, operation, entitlement.billable, state.get("usage_details"))
            await send(message)

        await self.app(scope, receive, metering_send)

    @staticmethod
    async def _record_usage(
        container: Container,
        tenant: TenantContext,
        operation: str,
        billable: bool,
        details: UsageDetails | None,
    ) -> None:
        try:
            await container.usage.record(
                tenant_id=tenant.tenant_id,
                api_key_id=tenant.api_key_id,
                operation_type=operation,
                billable=billable,
                details=details,
            )
        except Exception:
            # Verfügbarkeit vor Abrechnung: die Analyse wird trotzdem ausgeliefert,
            # der Ausfall muss aber alarmiert werden.
            logger.exception("USAGE_METERING_FAILED tenant=%s operation=%s", tenant.tenant_id, operation)
