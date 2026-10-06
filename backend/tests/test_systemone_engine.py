"""SystemOneDecisionEngine: Protokoll, Mapping, Fehlerpfade (MockTransport) und optional live gegen Ollama."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx2
import pytest

from app.config import Settings
from app.decision.base import DecisionEngineError, DecisionHints
from app.decision.heuristic_engine import HeuristicDecisionEngine
from app.decision.pipeline import DecisionPipeline
from app.decision.systemone_engine import QUESTIONS, SystemOneDecisionEngine, build_state
from app.schemas import TicketCategory

# Antwortformat, wie es Ollama 0.35.1 mit tev1 tatsächlich liefert (gekürzt).
OLLAMA_RESPONSE: dict[str, Any] = {
    "model": "tev1",
    "answers": {
        "category": {
            "type": "choice",
            "choice": "RETURN_OR_REFUND",
            "probabilities": {
                "WHERE_IS_MY_ORDER": 0.004,
                "RETURN_OR_REFUND": 0.9871,
                "PRODUCT_ISSUE": 0.003,
                "PAYMENT_OR_INVOICE": 0.004,
                "GENERAL_INQUIRY": 0.0019,
            },
            "confidence": 0.97,
        },
        "urgency": {
            "type": "score",
            "score": 2.91,
            "legend": {str(i): text for i, text in enumerate(QUESTIONS["urgency"]["criteria"])},
            "probabilities": {"0": 0.01, "1": 0.02, "2": 0.08, "3": 0.84, "4": 0.05},
            "confidence": 0.6,
        },
        "is_cancellation_request": {"type": "noul", "noul": 0.99},
    },
    "usage": {"input_tokens": 1510, "output_tokens": 3},
}


def _engine(handler: Any, **overrides: Any) -> SystemOneDecisionEngine:
    settings = Settings(decision_engine="systemone", **overrides)
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler), timeout=5)
    return SystemOneDecisionEngine(settings, client=client)


async def test_request_shape_and_mapping() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx2.Response(200, json=OLLAMA_RESPONSE)

    engine = _engine(handler, systemone_base_url="http://ollama:11434/", systemone_model="tev1:0.8b")
    decision = await engine.decide("Bitte storniert meine Bestellung!", DecisionHints(order_reference_detected=True))

    assert captured["url"] == "http://ollama:11434/v1/systemone"
    assert "authorization" not in captured["headers"]  # Ollama braucht keinen Key
    body = captured["body"]
    assert body["model"] == "tev1:0.8b"
    assert body["keep_alive"] == "30m"
    assert body["state"] == "Message:\nBitte storniert meine Bestellung!"
    assert list(body["questions"]) == ["category", "urgency", "is_cancellation_request"]
    assert list(body["questions"]["category"]["criteria"]) == [c.value for c in TicketCategory]
    assert all(isinstance(v, str) for v in body["questions"]["category"]["criteria"].values())
    assert len(body["questions"]["urgency"]["criteria"]) == 5

    assert decision.category is TicketCategory.RETURN_OR_REFUND
    assert decision.urgency == 4  # Stufe "3" (0-basiert) ist am wahrscheinlichsten
    assert decision.is_cancellation_request is True
    assert decision.contains_order_number is True  # deterministisch, nicht vom Modell
    assert decision.confidence == pytest.approx(0.9871)


async def test_typesafe_mode_sends_bearer_and_omits_keep_alive() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx2.Response(200, json={**OLLAMA_RESPONSE, "model": "jev-1.13.0"})

    engine = _engine(
        handler,
        systemone_base_url="https://api.typesafe.ai",
        systemone_api_key="ts_test",
        systemone_model="jev-latest",
        systemone_keep_alive="",
    )
    await engine.decide("Where is my parcel?", DecisionHints(subject="Order"))
    assert captured["headers"]["authorization"] == "Bearer ts_test"
    assert "keep_alive" not in captured["body"]
    assert captured["body"]["state"].startswith("Subject: Order\n\nMessage:\n")


def test_state_is_truncated_for_small_context() -> None:
    long_text = "Wort " * 2000
    state = build_state(long_text, None, max_chars=3000)
    assert len(state) < 3020
    assert state.endswith(" …")


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (404, {"error": "model 'tev1' not found"}, "ollama pull tev1"),
        (400, {"error": "prompt 0 has 2300 tokens; expected 1–2048 (input is never truncated)"}, "400"),
        (500, {"error": "model failed to load"}, "500"),
        (422, {"detail": [{"msg": "field required"}]}, "422"),
    ],
)
async def test_http_errors_raise_engine_error(status: int, body: dict[str, Any], expected: str) -> None:
    engine = _engine(lambda _: httpx2.Response(status, json=body))
    with pytest.raises(DecisionEngineError, match=expected):
        await engine.decide("Hallo", DecisionHints())


async def test_unknown_category_or_missing_answers_are_rejected() -> None:
    bad = json.loads(json.dumps(OLLAMA_RESPONSE))
    bad["answers"]["category"]["choice"] = "SOMETHING_ELSE"
    engine = _engine(lambda _: httpx2.Response(200, json=bad))
    with pytest.raises(DecisionEngineError, match="Schema"):
        await engine.decide("Hallo", DecisionHints())

    del bad["answers"]["urgency"]
    engine = _engine(lambda _: httpx2.Response(200, json=bad))
    with pytest.raises(DecisionEngineError):
        await engine.decide("Hallo", DecisionHints())


async def test_connection_errors_fall_back_to_heuristic() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("connection refused", request=request)

    pipeline = DecisionPipeline(primary=_engine(handler), fallback=HeuristicDecisionEngine())
    result = await pipeline.analyze("Der Mixer ist kaputt angekommen.")
    assert result.degraded is True
    assert result.engine == "heuristic-v1"
    assert result.decision.category is TicketCategory.PRODUCT_ISSUE


async def test_legal_threat_guardrail_overrides_low_model_urgency() -> None:
    low = json.loads(json.dumps(OLLAMA_RESPONSE))
    low["answers"]["urgency"]["probabilities"] = {"0": 0.1, "1": 0.2, "2": 0.6, "3": 0.05, "4": 0.05}
    pipeline = DecisionPipeline(primary=_engine(lambda _: httpx2.Response(200, json=low)))

    result = await pipeline.analyze("Ich warte seit Wochen. Jetzt schalte ich meinen Anwalt ein!")
    assert result.engine == "systemone:tev1"
    assert result.decision.urgency == 5

    calm = await pipeline.analyze("Wann kommt mein Paket?")
    assert calm.decision.urgency == 3


@pytest.mark.skipif(not os.environ.get("SYSTEMONE_LIVE_URL"), reason="SYSTEMONE_LIVE_URL nicht gesetzt")
async def test_live_against_ollama() -> None:
    """Optional: SYSTEMONE_LIVE_URL=http://localhost:11434 SYSTEMONE_LIVE_MODEL=tev1:0.8b pytest -k live"""
    settings = Settings(
        decision_engine="systemone",
        systemone_base_url=os.environ["SYSTEMONE_LIVE_URL"],
        systemone_model=os.environ.get("SYSTEMONE_LIVE_MODEL", "tev1"),
        systemone_timeout_seconds=300,
    )
    engine = SystemOneDecisionEngine(settings)
    try:
        decision = await engine.decide(
            "Hallo, bitte storniert sofort meine zweite Bestellung, bevor sie verschickt wird.", DecisionHints()
        )
    finally:
        await engine.aclose()
    assert decision.category is TicketCategory.RETURN_OR_REFUND
    assert decision.is_cancellation_request is True
