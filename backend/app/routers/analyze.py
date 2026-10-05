from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request

from app.container import Container
from app.decision.pipeline import AnalysisResult
from app.schemas import AnalyzeTicketRequest, AnalyzeTicketResponse, ErrorResponse, PiiReport, TicketFlags
from app.services.usage import UsageDetails

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
    response_model=AnalyzeTicketResponse,
    summary="Ticket/E-Mail in Echtzeit klassifizieren",
    responses={
        401: {"model": ErrorResponse, "description": "API-Key fehlt oder ist ungültig"},
        402: {"model": ErrorResponse, "description": "Kontingent erschöpft oder Abo inaktiv"},
        403: {"model": ErrorResponse, "description": "Origin für Publishable Key nicht freigegeben"},
        413: {"model": ErrorResponse, "description": "Text zu lang"},
        429: {"model": ErrorResponse, "description": "Rate-Limit erreicht"},
    },
)
async def analyze_ticket(payload: AnalyzeTicketRequest, request: Request) -> AnalyzeTicketResponse:
    # Authentifizierung, Mandanten-Zuordnung und Kontingent hat die ApiKeyAuthMiddleware
    # bereits erledigt (request.state.tenant).
    container: Container = request.app.state.container

    if len(payload.text) > container.settings.max_ticket_chars:
        raise HTTPException(
            status_code=413,
            detail=f"Der Text darf maximal {container.settings.max_ticket_chars} Zeichen lang sein.",
        )

    result = await container.pipeline.analyze(payload.text, payload.subject)

    # Wird von der Middleware nach erfolgreicher Antwort in usage_logs geschrieben.
    request.state.usage_details = UsageDetails(
        category=result.decision.category.value,
        urgency=result.decision.urgency,
        engine=result.engine,
        latency_ms=result.latency_ms,
    )
    return to_response(result, payload.external_id)
