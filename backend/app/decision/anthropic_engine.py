"""LLM-Decision-Engine auf Basis der Claude API mit nativen Structured Outputs.

Ein einziger Request (Single Pass): ``client.beta.messages.parse`` erzwingt das
JSON-Schema von :class:`TicketDecision` auf API-Seite und validiert die Antwort
lokal noch einmal mit Pydantic. Es wird kein Fließtext generiert – nur das
kompakte Entscheidungsobjekt.
"""

from __future__ import annotations

import logging

import anthropic
from anthropic import AsyncAnthropic
from pydantic import ValidationError

from app.config import Settings
from app.decision.base import DecisionEngineError, DecisionHints
from app.decision.prompt import SYSTEM_PROMPT, build_user_message
from app.schemas import TicketDecision

logger = logging.getLogger(__name__)

# Modelle, die den serverseitigen Refusal-Fallback ("default"-Routing) annehmen.
_SERVER_FALLBACK_MODELS = ("claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1")
_SERVER_FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Haiku 4.5 und ältere Modelle kennen den effort-Parameter nicht.
_NO_EFFORT_PREFIXES = ("claude-haiku", "claude-3", "claude-sonnet-4-5", "claude-opus-4-5", "claude-opus-4-1")


class AnthropicDecisionEngine:
    def __init__(self, settings: Settings, client: AsyncAnthropic | None = None) -> None:
        if client is None:
            if settings.anthropic_api_key is None:
                raise ValueError("ANTHROPIC_API_KEY ist nicht gesetzt.")
            client = AsyncAnthropic(
                api_key=settings.anthropic_api_key.get_secret_value(),
                timeout=settings.anthropic_timeout_seconds,
                max_retries=settings.anthropic_max_retries,
            )
        self._client = client
        self._model = settings.anthropic_model
        self.name = f"anthropic:{self._model}"
        self._request_options = self._build_request_options(settings)

    def _build_request_options(self, settings: Settings) -> dict[str, object]:
        options: dict[str, object] = {}
        model = self._model
        if settings.anthropic_effort and not model.startswith(_NO_EFFORT_PREFIXES):
            options["output_config"] = {"effort": settings.anthropic_effort}
        if settings.anthropic_server_fallbacks and model in _SERVER_FALLBACK_MODELS:
            # Lehnt ein Sicherheitsklassifikator ab, beantwortet das von Anthropic
            # empfohlene Fallback-Modell denselben Request – ohne zweiten Roundtrip.
            options["betas"] = [_SERVER_FALLBACK_BETA]
            options["fallbacks"] = "default"
        return options

    async def decide(self, text: str, hints: DecisionHints) -> TicketDecision:
        try:
            response = await self._client.beta.messages.parse(
                model=self._model,
                # Großzügig bemessen: Adaptive Thinking zählt mit, die Antwort selbst ist winzig.
                max_tokens=4096,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": build_user_message(text, hints.subject)}],
                output_format=TicketDecision,
                **self._request_options,  # type: ignore[arg-type]
            )
        except anthropic.APITimeoutError as exc:
            raise DecisionEngineError("LLM-Timeout") from exc
        except anthropic.RateLimitError as exc:
            raise DecisionEngineError("LLM-Rate-Limit erreicht") from exc
        except anthropic.APIStatusError as exc:
            logger.warning(
                "Claude API error status=%s request_id=%s", exc.status_code, exc.response.headers.get("request-id")
            )
            raise DecisionEngineError(f"LLM-API-Fehler ({exc.status_code})") from exc
        except anthropic.APIConnectionError as exc:
            raise DecisionEngineError("LLM nicht erreichbar") from exc
        except (ValidationError, ValueError) as exc:
            raise DecisionEngineError("LLM-Antwort entsprach nicht dem Schema") from exc

        if response.stop_reason == "refusal":
            category = response.stop_details.category if response.stop_details else None
            raise DecisionEngineError(f"LLM hat die Anfrage abgelehnt (category={category})")
        if response.stop_reason == "max_tokens":
            raise DecisionEngineError("LLM-Antwort wurde abgeschnitten (max_tokens)")

        decision = response.parsed_output
        if decision is None:
            raise DecisionEngineError("LLM lieferte kein strukturiertes Ergebnis")
        return decision

    async def aclose(self) -> None:
        await self._client.close()
