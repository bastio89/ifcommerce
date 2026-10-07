from __future__ import annotations

import json
from collections import deque

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestBodyLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        analysis_max_bytes: int,
        demo_max_bytes: int = 8 * 1024,
    ) -> None:
        self.app = app
        self._limits = {
            ("POST", "/api/v1/analyze-ticket"): analysis_max_bytes,
            ("POST", "/api/v1/demo/analyze-ticket"): demo_max_bytes,
        }

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "").rstrip("/")
        limit = self._limits.get((scope.get("method", ""), path))
        if limit is None:
            await self.app(scope, receive, send)
            return

        content_length = next((value for key, value in scope.get("headers", []) if key == b"content-length"), None)
        if content_length is not None and content_length.isdigit() and int(content_length) > limit:
            await self._send_error(send, limit)
            return

        messages: deque[Message] = deque()
        body_size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] == "http.request":
                body_size += len(message.get("body", b""))
                if body_size > limit:
                    await self._send_error(send, limit)
                    return
                messages.append(message)
                if not message.get("more_body", False):
                    break
            else:
                messages.append(message)

        async def replay_receive() -> Message:
            if messages:
                return messages.popleft()
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _send_error(send: Send, limit: int) -> None:
        body = json.dumps(
            {"error": {"code": "payload_too_large", "message": f"Request-Body überschreitet {limit} Bytes."}}
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
            }
        )
        await send({"type": "http.response.body", "body": body})
