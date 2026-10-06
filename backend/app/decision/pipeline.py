"""Orchestrierung: PII-Schutz -> Decision-Engine -> deterministische Leitplanken."""

from __future__ import annotations

import logging
import time
from collections import Counter
from dataclasses import dataclass

from app.decision.base import DecisionEngine, DecisionEngineError, DecisionHints
from app.decision.heuristic_engine import HeuristicDecisionEngine, detect_legal_threat
from app.privacy.pii import scrub_pii
from app.schemas import TicketDecision

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    decision: TicketDecision
    engine: str
    degraded: bool
    latency_ms: int
    pii_entities: dict[str, int]
    anonymized_text: str


class DecisionPipeline:
    def __init__(self, primary: DecisionEngine | None, fallback: HeuristicDecisionEngine | None = None) -> None:
        self._fallback = fallback or HeuristicDecisionEngine()
        self._primary: DecisionEngine = primary or self._fallback

    @property
    def engine_name(self) -> str:
        return self._primary.name

    @property
    def primary(self) -> DecisionEngine:
        return self._primary

    async def analyze(self, text: str, subject: str | None = None) -> AnalysisResult:
        started = time.perf_counter()

        # 1) DSGVO: Nichts verlässt den Prozess, bevor es anonymisiert wurde.
        body = scrub_pii(text)
        scrubbed_subject = scrub_pii(subject) if subject else None
        entities = Counter(body.entities)
        if scrubbed_subject is not None:
            entities.update(scrubbed_subject.entities)

        hints = DecisionHints(
            order_reference_detected=body.order_reference_detected
            or bool(scrubbed_subject and scrubbed_subject.order_reference_detected),
            subject=scrubbed_subject.text if scrubbed_subject else None,
        )

        # 2) Entscheidung im Single Pass; bei Störungen übernimmt die Heuristik.
        engine_name, degraded = self._primary.name, False
        try:
            decision = await self._primary.decide(body.text, hints)
        except DecisionEngineError as exc:
            logger.warning("Primary decision engine failed, using heuristic fallback: %s", exc)
            decision = await self._fallback.decide(body.text, hints)
            engine_name, degraded = self._fallback.name, True

        # 3) Leitplanken: deterministisch erkannte Fakten überstimmen das Modell.
        #    - Eine erkannte Bestellnummer ist ein harter Fakt.
        #    - Anwalts-, Klage-, Polizei- oder Betrugsdrohungen sind immer Stufe 5
        #      (kleine Decision-Modelle unterschätzen sie messbar).
        updates: dict[str, object] = {}
        if hints.order_reference_detected and not decision.contains_order_number:
            updates["contains_order_number"] = True
        if decision.urgency < 5 and detect_legal_threat(f"{hints.subject or ''}\n{body.text}"):
            updates["urgency"] = 5
        if updates:
            decision = decision.model_copy(update=updates)

        return AnalysisResult(
            decision=decision,
            engine=engine_name,
            degraded=degraded,
            latency_ms=int((time.perf_counter() - started) * 1000),
            pii_entities=dict(entities),
            anonymized_text=body.text,
        )
