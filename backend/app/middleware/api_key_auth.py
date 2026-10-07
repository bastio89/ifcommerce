"""ASGI-Middleware: API-Key-Validierung, Mandanten-Zuordnung und Rate-Limits.

Ablauf für geschützte Routen:

1. ``x-api-key`` gegen PostgreSQL validieren (mit kurzem Cache) -> TenantContext
2. Publishable Keys: Browser-Origin gegen die Allowlist des Keys prüfen
3. Rate-Limit pro Key (Token Bucket)
4. Tarif-/Kontingent-Prüfung und Usage-Metering erfolgen beim dauerhaften Job
    atomar mit dem Ergebnis.

Als reine ASGI-Middleware (statt BaseHTTPMiddleware) blockiert sie kein
Streaming und fügt praktisch keinen Overhead hinzu.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING

from starlette.types import ASGIApp, Receive, Scope, Send

from app.services.tenants import ApiKeyType

if TYPE_CHECKING:
    from app.container import Container

# Routen, die einen API-Key benötigen und selbst Tarif-/Usage-Regeln anwenden.
PROTECTED_ROUTES = {("POST", "/api/v1/analyze-ticket")}


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
        method = scope.get("method", "")
        path = scope.get("path", "").rstrip("/")
        is_protected_route = (method, path) in PROTECTED_ROUTES
        is_job_status = (
            method == "GET"
            and path.startswith("/api/v1/analysis-jobs/")
            and "/" not in path.removeprefix("/api/v1/analysis-jobs/")
        )
        if scope["type"] != "http" or (not is_protected_route and not is_job_status):
            # Nicht geschützt (inkl. CORS-Preflight und falscher Methoden -> 405 vom Router).
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
        allowed, retry_after = await container.rate_limiter.acquire(tenant.api_key_id, per_minute=per_minute)
        if not allowed:
            await _send_json(
                send,
                429,
                "rate_limited",
                "Zu viele Anfragen. Bitte später erneut versuchen.",
                {"retry-after": str(retry_after)},
            )
            return

        state = scope.setdefault("state", {})
        state["tenant"] = tenant
        state["api_key_id"] = tenant.api_key_id

        if not is_protected_route:
            await self.app(scope, receive, send)
            return

        await self.app(scope, receive, send)
