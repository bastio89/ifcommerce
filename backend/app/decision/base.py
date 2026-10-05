from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.schemas import TicketDecision


@dataclass(frozen=True, slots=True)
class DecisionHints:
    """Deterministische Signale aus der Vorverarbeitung (keine PII)."""

    order_reference_detected: bool = False
    subject: str | None = None


class DecisionEngineError(RuntimeError):
    """Die Engine konnte keine valide Entscheidung liefern (Timeout, Refusal, API-Fehler …)."""


class DecisionEngine(Protocol):
    name: str

    async def decide(self, text: str, hints: DecisionHints) -> TicketDecision: ...
