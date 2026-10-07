from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, Response, Security
from fastapi.responses import JSONResponse

from app.container import Container
from app.decision.pipeline import AnalysisResult
from app.schemas import (
    AnalysisJobAccepted,
    AnalyzeTicketRequest,
    AnalyzeTicketResponse,
    ErrorResponse,
    PiiReport,
    TicketFlags,
)
from app.security import API_KEY_HEADER
from app.services.analysis_jobs import AnalysisJobError

router = APIRouter(prefix="/api/v1", tags=["Decision API"])


def to_response(result: AnalysisResult, external_id: str | None) -> AnalyzeTicketResponse:
    decision = result.decision
    return AnalyzeTicketResponse(
        id=f"ana_{uuid.uuid4().hex}",
        external_id=external_id,
        category=decision.category,
        urgency=decision.urgency,
        flags=TicketFlags(
            is_cancellation_request=decision.is_cancellation_request,
            contains_order_number=decision.contains_order_number,
        ),
        confidence=round(decision.confidence, 3),
        engine=result.engine,
        degraded=result.degraded,
        latency_ms=result.latency_ms,
        pii=PiiReport(redacted=bool(result.pii_entities), entities=result.pii_entities),
        anonymized_text=result.anonymized_text,
    )


@router.post(
    "/analyze-ticket",
    response_model=AnalyzeTicketResponse | AnalysisJobAccepted,
    summary="Ticket/E-Mail in Echtzeit klassifizieren",
    responses={
        202: {"model": AnalysisJobAccepted, "description": "Analyse läuft asynchron weiter"},
        401: {"model": ErrorResponse, "description": "API-Key fehlt oder ist ungültig"},
        402: {"model": ErrorResponse, "description": "Kontingent erschöpft oder Abo inaktiv"},
        403: {"model": ErrorResponse, "description": "Origin für Publishable Key nicht freigegeben"},
        409: {"model": ErrorResponse, "description": "Idempotency-Key wurde mit anderem Inhalt wiederverwendet"},
        413: {"model": ErrorResponse, "description": "Text zu lang"},
        429: {"model": ErrorResponse, "description": "Rate-Limit erreicht"},
        503: {"model": ErrorResponse, "description": "Analyse konnte nicht abgeschlossen werden"},
    },
)
async def analyze_ticket(
    payload: AnalyzeTicketRequest,
    request: Request,
    response: Response,
    api_key: Annotated[str | None, Security(API_KEY_HEADER)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)] = None,
) -> AnalyzeTicketResponse | AnalysisJobAccepted | JSONResponse:
    # Authentifizierung, Mandanten-Zuordnung und Kontingent hat die ApiKeyAuthMiddleware
    # bereits erledigt (request.state.tenant).
    container: Container = request.app.state.container

    if len(payload.text) > container.settings.max_ticket_chars:
        raise HTTPException(
            status_code=413,
            detail=f"Der Text darf maximal {container.settings.max_ticket_chars} Zeichen lang sein.",
        )

    tenant = request.state.tenant
    try:
        job = await container.analysis_jobs.submit(
            tenant,
            api_key_id=request.state.api_key_id,
            text=payload.text,
            subject=payload.subject,
            external_id=payload.external_id,
            idempotency_key=idempotency_key,
        )
    except AnalysisJobError as exc:
        headers = {"retry-after": "1"} if exc.code == "analysis_queue_full" else None
        return JSONResponse(
            {"error": {"code": exc.code, "message": exc.message}},
            status_code=exc.status_code,
            headers=headers,
        )

    request.state.usage_handled = True
    job = (
        await container.analysis_jobs.wait(
            job.public_id,
            tenant.tenant_id,
            container.settings.analysis_sync_wait_seconds,
        )
        or job
    )
    if job.status in {"SUCCEEDED", "DEGRADED"} and job.result is not None:
        response.status_code = 200
        return AnalyzeTicketResponse.model_validate(job.result)
    if job.status == "FAILED":
        return JSONResponse(
            {"error": {"code": "analysis_failed", "message": "Analyse konnte nicht abgeschlossen werden."}},
            status_code=503,
        )

    response.status_code = 202
    response.headers["Retry-After"] = "1"
    return AnalysisJobAccepted(
        id=job.public_id,
        status=job.status.lower(),
        status_url=f"/api/v1/analysis-jobs/{job.public_id}",
    )
