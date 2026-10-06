"""Deterministische "System-1"-Engine: gewichtete Signalmuster (DE/EN), < 1 ms.

Dient als
* Fallback, wenn das LLM nicht erreichbar ist (Timeout, Rate-Limit, Refusal),
* Engine für lokale Entwicklung und Tests ohne API-Key,
* kostenlose Engine für den öffentlichen Live-Demo-Modus, falls gewünscht.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.decision.base import DecisionHints
from app.schemas import TicketCategory, TicketDecision


@dataclass(frozen=True, slots=True)
class _Signal:
    pattern: re.Pattern[str]
    weight: float


def _signals(*pairs: tuple[str, float]) -> tuple[_Signal, ...]:
    return tuple(_Signal(re.compile(p, re.IGNORECASE), w) for p, w in pairs)


_CATEGORY_SIGNALS: dict[TicketCategory, tuple[_Signal, ...]] = {
    TicketCategory.WHERE_IS_MY_ORDER: _signals(
        (r"\bwo\s+(?:ist|bleibt)\s+(?:mein|meine)\b", 3.0),
        (r"\bnoch\s+nicht\s+(?:angekommen|erhalten|geliefert|da|bekommen|zugestellt)", 3.0),
        (r"\bnicht\s+(?:angekommen|zugestellt|geliefert)", 2.5),
        (r"\b(?:liefer|versand|sendungs)status\b|\bsendungsverfolgung\b|\btracking", 2.5),
        (r"\bwann\s+(?:kommt|wird|erhalte|bekomme|kann\s+ich)", 2.0),
        (r"\blieferzeit|\blieferung|\bzustellung|\bversendet|\bverschickt|\bpaket", 1.2),
        (r"\b(?:dhl|dpd|hermes|gls|ups|fedex|usps)\b", 1.0),
        (r"\bwhere\s+is\s+my\b", 3.0),
        (
            r"\b(?:has\s*n[o']?t|has\s+not|did\s*n[o']?t|did\s+not|never|still\s+not)\s+(?:yet\s+)?"
            r"(?:arrived|been\s+delivered|received|shipped|come)",
            3.0,
        ),
        (r"\b(?:delivery|shipping|order)\s+status\b|\btrack(?:ing)?\s+(?:my\s+)?(?:order|package|parcel)", 2.5),
        (r"\bwhen\s+will\s+(?:my|it|the)\b", 2.0),
        (r"\b(?:package|parcel|shipment|delivery)\b", 1.0),
    ),
    TicketCategory.RETURN_OR_REFUND: _signals(
        (r"\br(?:ü|ue)ck(?:send|schick|gabe|erstatt)|\bretour|\bzur(?:ü|ue)ck(?:schicken|senden|geben)", 3.0),
        (r"\bumtausch|\bumtauschen|\btauschen\b", 2.5),
        (r"\berstattung|\berstatten|\bgeld\s+zur(?:ü|ue)ck|\bgutschrift", 3.0),
        (r"\bwiderruf", 3.0),
        (r"\bstorn(?:o|ieren|iere|ierung)|\bannullieren", 2.5),
        (r"\breturn(?:ing|s)?\b|\brefund|\bmoney\s+back|\bsend\s+(?:it\s+)?back", 3.0),
        (r"\bexchange\b|\bcancel(?:l?ation|l?ed|l?ing)?\b", 2.0),
    ),
    TicketCategory.PRODUCT_ISSUE: _signals(
        (r"\bdefekt|\bkaputt|\bbesch(?:ä|ae)digt|\bfehlerhaft|\bmangel|\bm(?:ä|ae)ngel", 3.0),
        (r"\bfunktioniert\s+nicht|\bgeht\s+nicht|\blässt\s+sich\s+nicht|\bfunktionslos", 3.0),
        (r"\bfalsche[nrs]?\s+(?:artikel|gr(?:ö|oe)(?:ß|ss)e|farbe|produkt|ware|modell)", 3.0),
        (r"\bfehlt\b|\bunvollst(?:ä|ae)ndig|\breklamation|\bgarantie|\bgew(?:ä|ae)hrleistung", 2.5),
        (r"\bqualit(?:ä|ae)t|\bverarbeitung|\bpasst\s+nicht", 1.5),
        (r"\bbroken\b|\bdamaged\b|\bdefective\b|\bfaulty\b|\bcracked\b", 3.0),
        (r"\b(?:does\s*n[o']?t|does\s+not|is\s*n[o']?t|stopped)\s+work", 3.0),
        (r"\bnot\s+working\b|\bwrong\s+(?:item|size|colou?r|product|model)\b|\bmissing\b", 3.0),
        (r"\bwarranty\b|\bquality\b", 1.5),
    ),
    TicketCategory.PAYMENT_OR_INVOICE: _signals(
        (r"\brechnung|\bquittung|\bbeleg\b", 2.5),
        (r"\bzahlung|\bbezahl|\bzahle\b|\bgezahlt|\babgebucht|\babbuchung|\bberechnet", 2.5),
        (r"\bdoppelt\s+(?:abgebucht|berechnet|bezahlt|belastet)", 3.5),
        (r"\b(?:ü|ue)berweisung|\bpaypal|\bkreditkarte|\blastschrift|\bklarna|\bsofort(?:ü|ue)berweisung", 2.0),
        (r"\bmahnung|\binkasso|\bmwst|\bust\b|\bumsatzsteuer", 2.5),
        (r"\bgutschein(?:code)?|\brabatt(?:code)?", 1.5),
        (r"\binvoice|\breceipt\b|\bbilling\b|\bbilled\b", 2.5),
        (r"\bpayment|\bpaid\b|\bcharged?\b|\bcredit\s+card|\bvat\b", 2.0),
        (r"\b(?:double|twice)\s+charged|\bcharged\s+twice", 3.5),
        (r"\bcoupon|\bdiscount\s+code|\bpromo\s+code", 1.5),
    ),
    TicketCategory.GENERAL_INQUIRY: _signals(
        (r"\bfrage\b|\binformation|\bauskunft|\bwissen\s+ob|\bgibt\s+es\b", 1.5),
        (r"\bverf(?:ü|ue)gbar|\bauf\s+lager|\blagernd|\bwieder\s+da|\bgr(?:ö|oe)(?:ß|ss)entabelle", 2.0),
        (r"\b(?:ö|oe)ffnungszeiten|\bnewsletter|\bpartnerschaft|\bkooperation|\bfiliale", 2.0),
        (r"\bquestion\b|\bwondering\b|\binformation\b|\bdo\s+you\s+(?:have|ship|offer|sell)", 1.5),
        (r"\bavailab|\bin\s+stock\b|\bback\s+in\s+stock|\bsize\s+(?:chart|guide)", 2.0),
    ),
}

_CANCELLATION = re.compile(
    r"\bstorn(?:o|ieren|iere|ierung|iert)|\bannullier|\bbestellung\s+(?:zur(?:ü|ue)ckziehen|aufheben)"
    r"|\bnicht\s+mehr\s+(?:haben|bekommen|erhalten)\s+(?:will|möchte|moechte)"
    r"|\bcancel(?:l?ation|l?ed|l?ing)?\b|\bcall\s+off\s+(?:my|the)\s+order",
    re.IGNORECASE,
)
_NEGATED_CANCELLATION = re.compile(
    r"\b(?:nicht|kein(?:e|en)?|nie|don't|do\s+not|not|never|no\s+need\s+to)\s+(?:\w+\s+){0,2}"
    r"(?:storn|annullier|cancel)",
    re.IGNORECASE,
)

_URGENCY_SIGNALS = _signals(
    # Rechtliche Drohungen / Eskalation -> sofort Stufe 5
    (r"\banwalt|\brechtsanwalt|\banw(?:ä|ae)ltin|\bklage\b|\bverklagen|\bvor\s+gericht|\bgerichtlich|\babmahnung", 5.0),
    (
        r"\bverbraucherzentrale|\bpolizei|\banzeige\s+(?:erstatten|wegen)|\bstrafanzeige|\bbetr(?:ü|ue)ger|\bist\s+(?:doch\s+|das\s+)?betrug\b",
        5.0,
    ),
    (r"\blawyer|\battorney|\blawsuit|\bsue\b|\bsuing\b|\blegal\s+action|\bcourt\b|\bfraud\b|\bscam\b", 5.0),
    (r"\bchargeback|\bdispute\s+(?:the\s+)?(?:charge|payment)|\br(?:ü|ue)ckbuchung|\bbank\s+zur(?:ü|ue)ckbuchen", 4.0),
    (r"\btrustpilot|\bschlechte\s+bewertung|\bbad\s+review|\bsocial\s+media", 3.0),
    # Ärger / Frustration
    (r"\bfrechheit|\bunversch(?:ä|ae)mt|\binakzeptabel|\bskandal|\bzumutung|\bunfassbar|\bkatastrophe", 2.5),
    (r"\bunacceptable|\bridiculous|\boutrageous|\bdisgusting|\bworst\b|\bterrible|\bfurious|\bangry", 2.5),
    (r"\bnie\s+wieder|\bnever\s+again|\bletzte\s+(?:mal|warnung)|\blast\s+time", 2.0),
    (
        r"\b(?:zum\s+)?(?:dritten|vierten|x-ten|wiederholten)\s+mal|\bschon\s+(?:mehrfach|mehrmals|wieder)"
        r"|\b(?:third|fourth|multiple)\s+time|\balready\s+(?:contacted|emailed|called|written)",
        2.0,
    ),
    # Zeitdruck
    (r"\bsofort|\bdringend|\bumgehend|\beilt\b|\bschnellstm(?:ö|oe)glich|\bheute\s+noch", 1.5),
    (r"\burgent|\basap\b|\bimmediately|\bright\s+now|\bas\s+soon\s+as\s+possible", 1.5),
    (
        r"\bseit\s+(?:\d+|zwei|drei|vier|mehreren)\s+(?:wochen|tagen|monaten)"
        r"|\bfor\s+(?:\d+|two|three|several)\s+(?:weeks|days|months)",
        1.0,
    ),
)


_LEGAL_THREAT_SIGNALS = tuple(s for s in _URGENCY_SIGNALS if s.weight >= 5.0)


def detect_legal_threat(text: str) -> bool:
    """Hochpräzises Signal für Anwalts-, Klage-, Polizei- oder Betrugsdrohungen (DE/EN)."""
    return any(signal.pattern.search(text) for signal in _LEGAL_THREAT_SIGNALS)


class HeuristicDecisionEngine:
    name = "heuristic-v1"

    async def decide(self, text: str, hints: DecisionHints) -> TicketDecision:
        return self.decide_sync(text, hints)

    def decide_sync(self, text: str, hints: DecisionHints) -> TicketDecision:
        haystack = f"{hints.subject or ''}\n{text}"

        scores = {
            category: sum(s.weight for s in signals if s.pattern.search(haystack))
            for category, signals in _CATEGORY_SIGNALS.items()
        }

        cancellation = bool(_CANCELLATION.search(haystack)) and not _NEGATED_CANCELLATION.search(haystack)
        if cancellation:
            # Reine Stornowünsche laufen fachlich über den Rückerstattungs-Prozess.
            scores[TicketCategory.RETURN_OR_REFUND] += 2.0

        total = sum(scores.values())
        if total == 0:
            category, confidence = TicketCategory.GENERAL_INQUIRY, 0.4
        else:
            category = max(scores, key=lambda c: scores[c])
            share = scores[category] / total
            # Sättigung: mehr Evidenz -> höhere Sicherheit, gedeckelt bei 0.95.
            evidence = min(scores[category] / 6.0, 1.0)
            confidence = round(min(0.95, 0.35 + 0.35 * share + 0.25 * evidence), 2)

        return TicketDecision(
            category=category,
            urgency=self._urgency(haystack, category, cancellation),
            is_cancellation_request=cancellation,
            contains_order_number=hints.order_reference_detected,
            confidence=confidence,
        )

    @staticmethod
    def _urgency(text: str, category: TicketCategory, cancellation: bool) -> int:
        base = {
            TicketCategory.GENERAL_INQUIRY: 1.0,
            TicketCategory.RETURN_OR_REFUND: 2.0,
            TicketCategory.PAYMENT_OR_INVOICE: 2.0,
            TicketCategory.WHERE_IS_MY_ORDER: 2.0,
            TicketCategory.PRODUCT_ISSUE: 2.5,
        }[category]

        hits = [s.weight for s in _URGENCY_SIGNALS if s.pattern.search(text)]
        if any(weight >= 5.0 for weight in hits):
            return 5

        score = base + 0.6 * sum(hits)
        exclamations = text.count("!")
        score += min(exclamations, 6) * 0.25
        letters = [ch for ch in text if ch.isalpha()]
        if len(letters) > 20 and sum(ch.isupper() for ch in letters) / len(letters) > 0.5:
            score += 1.5  # GESCHRIEN
        if cancellation:
            score = max(score, 4.0)  # Storno muss vor dem Versand bearbeitet werden

        return int(max(1, min(5, round(score))))
