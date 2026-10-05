"""Live-Demo der Landingpage.

Nur über den Next.js-Server erreichbar (geteiltes ``INTERNAL_API_SECRET``);
Rate-Limiting pro Besucher-IP passiert dort. Demo-Aufrufe werden nicht gemessen.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.container import Container
from app.routers.analyze import to_response
from app.schemas import AnalyzeTicketResponse
from app.security import constant_time_equals

router = APIRouter(prefix="/api/v1/demo", tags=["Live-Demo (intern)"], include_in_schema=False)

DEMO_MAX_CHARS = 2_000


class DemoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=DEMO_MAX_CHARS)


@router.post("/analyze-ticket", response_model=AnalyzeTicketResponse)
async def demo_analyze(
    payload: DemoRequest,
    request: Request,
    x_internal_secret: str | None = Header(default=None),
) -> AnalyzeTicketResponse:
    container: Container = request.app.state.container
    expected = container.settings.internal_api_secret
    if (
        expected is None
        or not x_internal_secret
        or not constant_time_equals(x_internal_secret, expected.get_secret_value())
    ):
        raise HTTPException(status_code=403, detail="Interner Endpunkt.")

    result = await container.pipeline.analyze(payload.text)
    return to_response(result, external_id=None)
