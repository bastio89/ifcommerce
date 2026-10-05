"""Öffentliche API-Verträge (Pydantic v2)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TicketCategory(StrEnum):
    WHERE_IS_MY_ORDER = "WHERE_IS_MY_ORDER"
    RETURN_OR_REFUND = "RETURN_OR_REFUND"
    PRODUCT_ISSUE = "PRODUCT_ISSUE"
    PAYMENT_OR_INVOICE = "PAYMENT_OR_INVOICE"
    GENERAL_INQUIRY = "GENERAL_INQUIRY"


class TicketDecision(BaseModel):
    """Das Ergebnis des Decision-Modells – exakt ein Durchlauf, exakt dieses Schema."""

    model_config = ConfigDict(extra="forbid")

    category: TicketCategory = Field(description="Primäres Anliegen des Kunden.")
    urgency: int = Field(
        ge=1,
        le=5,
        description="1 = niedrig, 5 = Kundenwut oder rechtliche Drohung.",
    )
    is_cancellation_request: bool = Field(description="True, wenn der Kunde eine Bestellung sofort stornieren möchte.")
    contains_order_number: bool = Field(
        description="True, wenn der Text eine Bestell-, Auftrags- oder Rechnungsnummer enthält."
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Sicherheit der Klassifikation.")


class AnalyzeTicketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1, description="Roher, unstrukturierter Nachrichtentext.")
    subject: str | None = Field(default=None, max_length=500, description="Optionaler Betreff.")
    external_id: str | None = Field(
        default=None,
        max_length=200,
        description="Optionale Ticket-/Nachrichten-ID im System des Händlers (wird zurückgegeben).",
    )


class TicketFlags(BaseModel):
    is_cancellation_request: bool
    contains_order_number: bool


class PiiReport(BaseModel):
    redacted: bool
    entities: dict[str, int] = Field(
        description="Anzahl der anonymisierten Entitäten je Typ (z. B. EMAIL, PHONE, NAME)."
    )


class AnalyzeTicketResponse(BaseModel):
    id: str = Field(description="Eindeutige ID dieser Analyse.")
    external_id: str | None = None
    category: TicketCategory
    urgency: int
    flags: TicketFlags
    confidence: float
    engine: str = Field(description="Welche Decision-Engine entschieden hat.")
    degraded: bool = Field(description="True, wenn das LLM nicht verfügbar war und die Heuristik übernommen hat.")
    latency_ms: int
    pii: PiiReport
    anonymized_text: str = Field(description="Der Text, wie ihn das Decision-Modell gesehen hat.")


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
