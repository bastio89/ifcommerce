/** Antwort von POST /api/v1/analyze-ticket (siehe backend/app/schemas.py). */
export type TicketCategory =
  | "WHERE_IS_MY_ORDER"
  | "RETURN_OR_REFUND"
  | "PRODUCT_ISSUE"
  | "PAYMENT_OR_INVOICE"
  | "GENERAL_INQUIRY";

export type AnalyzeResult = {
  id: string;
  external_id: string | null;
  category: TicketCategory;
  urgency: number;
  flags: { is_cancellation_request: boolean; contains_order_number: boolean };
  confidence: number;
  engine: string;
  degraded: boolean;
  latency_ms: number;
  pii: { redacted: boolean; entities: Record<string, number> };
  anonymized_text: string;
};

export type ApiError = { error: { code: string; message: string } };
