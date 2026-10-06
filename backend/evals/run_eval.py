"""Misst eine Decision-Engine auf gelabelten Tickets – vor jedem Modellwechsel ausführen.

Beispiele (im Ordner backend/):
    python -m evals.run_eval --engine heuristic
    DECISION_ENGINE=systemone SYSTEMONE_MODEL=tev1:0.8b python -m evals.run_eval --engine systemone
    python -m evals.run_eval --engine systemone --tickets meine_tickets.jsonl --json ergebnis.json

Format der Ticket-Datei (JSON Lines): {"text", "subject"?, "category", "urgency" (1-5), "cancel" (bool)}.
Die mitgelieferten 30 Tickets sind synthetische Beispiele. Aussagekräftig wird die
Messung erst mit echten (anonymisierten) Tickets deines Shops.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
from pathlib import Path
from typing import Any

from app.config import Settings
from app.decision.heuristic_engine import HeuristicDecisionEngine
from app.decision.pipeline import DecisionPipeline
from app.main import build_primary_engine

DEFAULT_TICKETS = Path(__file__).with_name("tickets.jsonl")


def _load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


async def evaluate(engine: str, tickets: list[dict[str, Any]]) -> dict[str, Any]:
    settings = Settings(decision_engine=engine)  # übrige Werte aus ENV/.env
    primary = build_primary_engine(settings)
    pipeline = DecisionPipeline(primary=primary, fallback=HeuristicDecisionEngine())

    warm_up = getattr(primary, "warm_up", None)
    if warm_up is not None:
        await warm_up()  # Ladezeit des Modells nicht mitmessen

    rows: list[dict[str, Any]] = []
    try:
        for ticket in tickets:
            result = await pipeline.analyze(ticket["text"], ticket.get("subject"))
            decision = result.decision
            rows.append(
                {
                    "text": ticket["text"][:60],
                    "category": (decision.category.value, ticket["category"]),
                    "urgency": (decision.urgency, ticket["urgency"]),
                    "cancel": (decision.is_cancellation_request, ticket["cancel"]),
                    "latency_ms": result.latency_ms,
                    "degraded": result.degraded,
                }
            )
    finally:
        close = getattr(primary, "aclose", None)
        if close is not None:
            await close()

    n = len(rows)
    tp = sum(1 for r in rows if r["cancel"] == (True, True))
    fp = sum(1 for r in rows if r["cancel"] == (True, False))
    fn = sum(1 for r in rows if r["cancel"] == (False, True))
    latencies = sorted(r["latency_ms"] for r in rows)
    return {
        "engine": pipeline.engine_name,
        "tickets": n,
        "category_accuracy": sum(r["category"][0] == r["category"][1] for r in rows) / n,
        "urgency_exact": sum(r["urgency"][0] == r["urgency"][1] for r in rows) / n,
        "urgency_within_1": sum(abs(r["urgency"][0] - r["urgency"][1]) <= 1 for r in rows) / n,
        "cancel_precision": tp / (tp + fp) if tp + fp else None,
        "cancel_recall": tp / (tp + fn) if tp + fn else None,
        "latency_ms_median": statistics.median(latencies),
        "latency_ms_p95": latencies[max(0, round(0.95 * n) - 1)],
        "fallbacks": sum(r["degraded"] for r in rows),
        "errors": [r for r in rows if r["category"][0] != r["category"][1] or r["cancel"][0] != r["cancel"][1]],
    }


def _fmt(value: float | None) -> str:
    return "–" if value is None else f"{value:.0%}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--engine", choices=["heuristic", "systemone", "anthropic"], default="heuristic")
    parser.add_argument("--tickets", type=Path, default=DEFAULT_TICKETS)
    parser.add_argument("--json", type=Path, help="Ergebnis zusätzlich als JSON speichern")
    args = parser.parse_args()

    report = asyncio.run(evaluate(args.engine, _load(args.tickets)))
    print(f"Engine:              {report['engine']}  ({report['tickets']} Tickets)")
    print(f"Kategorie korrekt:   {_fmt(report['category_accuracy'])}")
    print(f"Dringlichkeit exakt: {_fmt(report['urgency_exact'])}   (±1: {_fmt(report['urgency_within_1'])})")
    print(f"Storno Precision:    {_fmt(report['cancel_precision'])}   Recall: {_fmt(report['cancel_recall'])}")
    print(f"Latenz Median / p95: {report['latency_ms_median']:.0f} ms / {report['latency_ms_p95']:.0f} ms")
    print(f"Fallbacks:           {report['fallbacks']}")
    for row in report["errors"]:
        print(
            f"  ✗ {row['text']!r}: Kategorie {row['category'][0]} (soll {row['category'][1]}), "
            f"Storno {row['cancel'][0]} (soll {row['cancel'][1]})"
        )
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
