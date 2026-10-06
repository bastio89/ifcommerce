"""Decision-Engine für "System One"-Modelle: lokal über Ollama (Tev1) oder gehostet (TypeSafe Jev).

Beide sprechen dasselbe Protokoll ``POST /v1/systemone``: Statt Text zu generieren,
beantwortet das Modell typisierte Fragen mit Wahrscheinlichkeiten (choice, noul, score).
Damit braucht DecideCommerce keinen LLM-Anbieter; mit Ollama verlässt kein Ticket die
eigene Infrastruktur.

Protokoll-Hinweise (Ollama 0.35.x, verifiziert gegen einen laufenden Server):
* Jede Frage wird als eigener Prompt bewertet, der den vollständigen ``state`` und das
  Schema ALLER Fragen enthält. Tev1 hat ~2.048 Tokens Kontext pro Prompt und kürzt nie
  selbst – deshalb wird der Text hier begrenzt und es werden nur drei Fragen gestellt.
* ``contains_order_number`` wird deterministisch (Regex der PII-Schicht) bestimmt, nicht
  vom Modell – Zählen/Extrahieren ist eine dokumentierte Schwäche dieser Modellklasse.
* Fragenamen und Optionsschlüssel sind für das Modell sichtbar und daher sprechend.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx2
from pydantic import BaseModel, ConfigDict, ValidationError

from app.config import Settings
from app.decision.base import DecisionEngineError, DecisionHints
from app.schemas import TicketCategory, TicketDecision

logger = logging.getLogger(__name__)

# Englische Anweisungen: Tev1 und Jev sind primär auf Englisch trainiert, verstehen den
# (deutschen) Ticket-Text im state aber. GENERAL_INQUIRY steht als Auffangoption zuletzt,
# weil diese Modelle bei Gleichstand zur ersten Option tendieren.
QUESTIONS: dict[str, dict[str, Any]] = {
    "category": {
        "type": "choice",
        "instructions": "What is the customer's main concern in this support message?",
        "criteria": {
            TicketCategory.WHERE_IS_MY_ORDER.value: (
                "Delivery status, a late or missing parcel, tracking or shipping time."
            ),
            TicketCategory.RETURN_OR_REFUND.value: (
                "Returning or exchanging an item, getting money back, or cancelling an order."
            ),
            TicketCategory.PRODUCT_ISSUE.value: (
                "A defective, damaged, wrong or incomplete product, or a quality or warranty problem."
            ),
            TicketCategory.PAYMENT_OR_INVOICE.value: (
                "Invoices, payment methods, failed or double charges, vouchers or discount codes."
            ),
            TicketCategory.GENERAL_INQUIRY.value: (
                "Anything else, such as product availability, sizing or pre-sales questions."
            ),
        },
    },
    "urgency": {
        "type": "score",
        "instructions": "How urgently must the shop act on this message?",
        "criteria": [
            "Low: neutral question, no time pressure.",
            "Normal: standard service request.",
            "Elevated: a problem affecting the customer, mild frustration.",
            "High: strong frustration, repeated contact, or time-critical (e.g. cancel before shipping).",
            "Critical: open anger with escalation or a legal threat (lawyer, chargeback, fraud, police).",
        ],
    },
    "is_cancellation_request": {
        "type": "noul",
        "instructions": "Does the customer ask to cancel an order now, before or during fulfilment?",
        "criteria": {
            "true": "The customer wants an order cancelled.",
            "false": "No cancellation is requested (returning an already received item is not a cancellation).",
        },
    },
}


class _ChoiceAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore")
    choice: str
    probabilities: dict[str, float] = {}
    confidence: float | None = None


class _ScoreAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore")
    score: float
    probabilities: dict[str, float] = {}


class _NoulAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore")
    noul: float


class _Answers(BaseModel):
    model_config = ConfigDict(extra="ignore")
    category: _ChoiceAnswer
    urgency: _ScoreAnswer
    is_cancellation_request: _NoulAnswer


class _SystemOneResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    model: str | None = None
    answers: _Answers


def build_state(text: str, subject: str | None, max_chars: int) -> str:
    """Kompakter Klartext-State (ein JSON-Objekt würde doppelt escaped und Tokens kosten)."""
    body = text.strip()
    if len(body) > max_chars:
        cut = body[:max_chars]
        body = (cut.rsplit(" ", 1)[0] if " " in cut[-40:] else cut) + " …"
    return f"Subject: {subject.strip()}\n\nMessage:\n{body}" if subject else f"Message:\n{body}"


def _urgency_level(answer: _ScoreAnswer, levels: int) -> int:
    """Wahrscheinlichste Stufe (0-basiert) -> 1..5. Der Erwartungswert dient nur als Fallback."""
    if answer.probabilities:
        best = max(answer.probabilities.items(), key=lambda item: item[1])[0]
        try:
            index = int(best)
        except ValueError:
            index = round(answer.score)
    else:
        index = round(answer.score)
    return max(1, min(levels, index + 1))


def _error_message(response: httpx2.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(body, dict):
        if isinstance(body.get("error"), str):  # Ollama
            return body["error"]
        if "detail" in body:  # TypeSafe (FastAPI-Validierung)
            return str(body["detail"])[:200]
    return str(body)[:200]


class SystemOneDecisionEngine:
    def __init__(self, settings: Settings, client: httpx2.AsyncClient | None = None) -> None:
        self._model = settings.systemone_model
        self.name = f"systemone:{self._model}"
        self._url = settings.systemone_base_url.rstrip("/") + "/v1/systemone"
        self._keep_alive = settings.systemone_keep_alive or None
        self._max_state_chars = settings.systemone_max_state_chars
        self._cancel_threshold = settings.systemone_cancellation_threshold
        self._warmup_timeout = settings.systemone_warmup_timeout_seconds
        headers = {"content-type": "application/json", "accept": "application/json"}
        if settings.systemone_api_key is not None and settings.systemone_api_key.get_secret_value():
            # TypeSafe (oder ein Auth-Proxy vor Ollama) erwartet einen Bearer-Token.
            headers["authorization"] = f"Bearer {settings.systemone_api_key.get_secret_value()}"
        self._client = client or httpx2.AsyncClient(timeout=settings.systemone_timeout_seconds)
        self._headers = headers

    def _payload(self, state: str) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self._model, "state": state, "questions": QUESTIONS}
        if self._keep_alive is not None:
            payload["keep_alive"] = self._keep_alive  # Ollama: Modell geladen halten
        return payload

    async def _post(self, state: str, *, request_timeout: float | None = None) -> dict[str, Any]:
        extra: dict[str, Any] = {"timeout": request_timeout} if request_timeout is not None else {}
        try:
            response = await self._client.post(self._url, json=self._payload(state), headers=self._headers, **extra)
        except httpx2.TimeoutException as exc:
            raise DecisionEngineError("Decision-Modell: Timeout") from exc
        except httpx2.HTTPError as exc:
            raise DecisionEngineError(f"Decision-Modell nicht erreichbar ({type(exc).__name__})") from exc

        if response.status_code != 200:
            message = _error_message(response)
            if response.status_code == 404:
                message += f" – Modell mit `ollama pull {self._model}` laden"
            raise DecisionEngineError(f"Decision-Modell-Fehler {response.status_code}: {message}")
        try:
            return response.json()
        except ValueError as exc:
            raise DecisionEngineError("Decision-Modell lieferte kein JSON") from exc

    async def decide(self, text: str, hints: DecisionHints) -> TicketDecision:
        state = build_state(text, hints.subject, self._max_state_chars)
        raw = await self._post(state)
        try:
            answers = _SystemOneResponse.model_validate(raw).answers
            category = TicketCategory(answers.category.choice)
        except (ValidationError, ValueError) as exc:
            raise DecisionEngineError("Antwort des Decision-Modells entsprach nicht dem Schema") from exc

        confidence = answers.category.probabilities.get(category.value, answers.category.confidence or 0.0)
        return TicketDecision(
            category=category,
            urgency=_urgency_level(answers.urgency, len(QUESTIONS["urgency"]["criteria"])),
            is_cancellation_request=answers.is_cancellation_request.noul >= self._cancel_threshold,
            contains_order_number=hints.order_reference_detected,
            confidence=round(max(0.0, min(1.0, confidence)), 4),
        )

    async def warm_up(self) -> None:
        """Lädt das Modell beim Start vor (Ollama braucht beim ersten Aufruf deutlich länger)."""
        try:
            await self._post("Message:\nHello, where is my parcel?", request_timeout=self._warmup_timeout)
            logger.info("Decision model %s is loaded and ready", self._model)
        except DecisionEngineError as exc:
            logger.warning("Decision model warm-up failed: %s", exc)

    async def aclose(self) -> None:
        await self._client.aclose()
