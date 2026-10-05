from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.container import Container

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Liveness")
async def health(request: Request) -> dict[str, str]:
    container: Container = request.app.state.container
    return {"status": "ok", "engine": container.pipeline.engine_name}


@router.get("/health/ready", summary="Readiness (inkl. Datenbank)")
async def ready(request: Request) -> JSONResponse:
    container: Container = request.app.state.container
    try:
        await container.pool.fetchval("SELECT 1")
    except Exception:
        return JSONResponse({"status": "unavailable", "database": "down"}, status_code=503)
    return JSONResponse({"status": "ok", "database": "up"})
