"""Prüft das exakte Request-Format gegen die Claude API – ohne Netzwerk (MockTransport)."""

from __future__ import annotations

import json
from typing import Any

import httpx2
import pytest
from anthropic import AsyncAnthropic, DefaultAsyncHttpxClient

from app.config import Settings
from app.decision.anthropic_engine import AnthropicDecisionEngine
from app.decision.base import DecisionEngineError, DecisionHints
from app.decision.heuristic_engine import HeuristicDecisionEngine
from app.decision.pipeline import DecisionPipeline
from app.schemas import TicketCategory

DECISION = {
    "category": "RETURN_OR_REFUND",
    "urgency": 4,
    "is_cancellation_request": True,
    "contains_order_number": False,
    "confidence": 0.93,
}


def _message(content: list[dict[str, Any]], stop_reason: str = "end_turn") -> dict[str, Any]:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 420, "output_tokens": 40},
    }


def _engine(model: str, handler: Any) -> AnthropicDecisionEngine:
    client = AsyncAnthropic(
        api_key="sk-ant-test",
        max_retries=0,
        http_client=DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler)),
    )
    return AnthropicDecisionEngine(Settings(anthropic_model=model, anthropic_api_key="sk-ant-test"), client=client)


async def test_single_pass_structured_output_request() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["body"] = json.loads(request.content)
        captured["beta"] = request.headers.get("anthropic-beta", "")
        return httpx2.Response(200, json=_message([{"type": "text", "text": json.dumps(DECISION)}]))

    engine = _engine("claude-opus-5-5", handler)
    decision = await engine.decide("Bitte Bestellung stornieren!", DecisionHints(subject="Storno"))

    assert decision.category is TicketCategory.RETURN_OR_REFUND
    assert decision.is_cancellation_request is True

    body = captured["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in captured["beta"]
    assert body["output_config"]["effort"] == "low"
    schema = body["output_config"]["format"]["schema"]
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert set(schema["required"]) == set(DECISION)
    assert "thinking" not in body  # Opus 5.5: Adaptive Thinking ist Standard, Effort steuert die Tiefe
    assert "<customer_message>" in body["messages"][0]["content"]
    assert "<subject>\nStorno\n</subject>" in body["messages"][0]["content"]


async def test_models_without_effort_or_fallback_support() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["body"] = json.loads(request.content)
        return httpx2.Response(200, json=_message([{"type": "text", "text": json.dumps(DECISION)}]))

    await _engine("claude-haiku-4-5", handler).decide("Test", DecisionHints())
    assert "fallbacks" not in captured["body"]
    assert "effort" not in captured["body"].get("output_config", {})


async def test_refusal_raises_engine_error() -> None:
    def handler(_: httpx2.Request) -> httpx2.Response:
        payload = _message([], stop_reason="refusal")
        payload["stop_details"] = {"type": "refusal", "category": "cyber", "explanation": None}
        return httpx2.Response(200, json=payload)

    with pytest.raises(DecisionEngineError, match="abgelehnt"):
        await _engine("claude-opus-5-5", handler).decide("Test", DecisionHints())


async def test_api_errors_fall_back_to_heuristic() -> None:
    def handler(_: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(529, json={"type": "error", "error": {"type": "overloaded_error", "message": "x"}})

    pipeline = DecisionPipeline(primary=_engine("claude-opus-5-5", handler), fallback=HeuristicDecisionEngine())
    result = await pipeline.analyze("Wo ist meine Bestellung #4711? Mein Name ist Max Mustermann.")

    assert result.degraded is True
    assert result.engine == "heuristic-v1"
    assert result.decision.category is TicketCategory.WHERE_IS_MY_ORDER
    assert result.decision.contains_order_number is True
    assert "Mustermann" not in result.anonymized_text


async def test_pii_never_reaches_the_llm() -> None:
    seen: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(json.loads(request.content)["messages"][0]["content"])
        return httpx2.Response(200, json=_message([{"type": "text", "text": json.dumps(DECISION)}]))

    pipeline = DecisionPipeline(primary=_engine("claude-opus-5-5", handler))
    await pipeline.analyze(
        "Storno bitte! max@example.com, Tel. 0171 1234567, Herr Müller",
        subject="Anfrage von Herrn Müller",
    )
    assert seen, "LLM wurde nicht aufgerufen"
    for forbidden in ("max@example.com", "1234567", "Müller"):
        assert forbidden not in seen[0]
