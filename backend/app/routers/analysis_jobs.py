from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, Response, Security

from app.container import Container
from app.schemas import AnalysisJobStatusResponse, AnalyzeTicketResponse, ErrorBody, ErrorResponse
from app.security import API_KEY_HEADER

router = APIRouter(prefix="/api/v1/analysis-jobs", tags=["Analysis jobs"])


@router.get(
    "/{job_id}",
    response_model=AnalysisJobStatusResponse,
    responses={
        401: {"model": ErrorResponse, "description": "API-Key fehlt oder ist ungültig"},
        403: {"model": ErrorResponse, "description": "Origin für Publishable Key nicht freigegeben"},
        404: {"model": ErrorResponse, "description": "Job nicht gefunden oder abgelaufen"},
        429: {"model": ErrorResponse, "description": "Rate-Limit erreicht"},
    },
)
async def get_analysis_job(
    job_id: str,
    request: Request,
    response: Response,
    api_key: Annotated[str | None, Security(API_KEY_HEADER)],
) -> AnalysisJobStatusResponse:
    container: Container = request.app.state.container
    tenant = request.state.tenant
    job = await container.analysis_jobs.get(job_id, tenant.tenant_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Analyseauftrag nicht gefunden oder abgelaufen.")

    status = job.status.lower()
    if status in {"queued", "processing"}:
        response.headers["Retry-After"] = "1"
    return AnalysisJobStatusResponse(
        id=job.public_id,
        status=status,
        created_at=job.created_at,
        expires_at=job.expires_at,
        result=AnalyzeTicketResponse.model_validate(job.result) if job.result is not None else None,
        error=(
            ErrorBody(code=job.error_code or "analysis_failed", message="Analyse konnte nicht abgeschlossen werden.")
            if status == "failed"
            else None
        ),
    )
