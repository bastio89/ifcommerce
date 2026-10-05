import { Check, Minus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { AnalyzeResult, TicketCategory } from "@/lib/types";
import { cn } from "@/lib/utils";

export const CATEGORY_META: Record<TicketCategory, { label: string; hint: string }> = {
  WHERE_IS_MY_ORDER: { label: "Wo ist meine Bestellung?", hint: "Versand & Tracking" },
  RETURN_OR_REFUND: { label: "Retoure / Erstattung", hint: "Rücksendung, Storno, Geld zurück" },
  PRODUCT_ISSUE: { label: "Produktproblem", hint: "Defekt, falscher Artikel, Qualität" },
  PAYMENT_OR_INVOICE: { label: "Zahlung / Rechnung", hint: "Abbuchung, Rechnung, Gutschein" },
  GENERAL_INQUIRY: { label: "Allgemeine Anfrage", hint: "Vorverkauf, Verfügbarkeit" },
};

const URGENCY = [
  { label: "Niedrig", tone: "neutral", bar: "bg-secondary" },
  { label: "Normal", tone: "neutral", bar: "bg-secondary" },
  { label: "Erhöht", tone: "warning", bar: "bg-warning" },
  { label: "Hoch", tone: "serious", bar: "bg-serious" },
  { label: "Kritisch", tone: "critical", bar: "bg-critical" },
] as const;

export function UrgencyMeter({ value }: { value: number }) {
  const level = URGENCY[Math.min(Math.max(value, 1), 5) - 1]!;
  return (
    <div className="flex items-center gap-3">
      <div className="flex gap-1" role="img" aria-label={`Dringlichkeit ${value} von 5`}>
        {[1, 2, 3, 4, 5].map((step) => (
          <span
            key={step}
            className={cn("h-2 w-6 rounded-full", step <= value ? level.bar : "bg-white/10")}
          />
        ))}
      </div>
      <Badge tone={level.tone}>
        {value}/5 · {level.label}
      </Badge>
    </div>
  );
}

function Flag({ label, active }: { label: string; active: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background/60 px-3 py-2">
      <span className="font-mono text-[12px] text-secondary">{label}</span>
      <span
        className={cn(
          "inline-flex items-center gap-1 text-xs font-medium",
          active ? "text-accent-strong" : "text-muted",
        )}
      >
        {active ? <Check className="size-3.5" aria-hidden /> : <Minus className="size-3.5" aria-hidden />}
        {active ? "true" : "false"}
      </span>
    </div>
  );
}

export function DecisionSummary({ result }: { result: AnalyzeResult }) {
  const category = CATEGORY_META[result.category];
  const confidence = Math.round(result.confidence * 100);
  const piiEntries = Object.entries(result.pii.entities);

  return (
    <div className="flex flex-col gap-5">
      <div>
        <div className="mb-1.5 text-xs uppercase tracking-wider text-muted">Kategorie</div>
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="text-lg font-semibold">{category.label}</span>
          <span className="font-mono text-xs text-muted">{result.category}</span>
        </div>
        <div className="text-[13px] text-muted">{category.hint}</div>
      </div>

      <div>
        <div className="mb-2 text-xs uppercase tracking-wider text-muted">Dringlichkeit</div>
        <UrgencyMeter value={result.urgency} />
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <Flag label="is_cancellation_request" active={result.flags.is_cancellation_request} />
        <Flag label="contains_order_number" active={result.flags.contains_order_number} />
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between text-xs uppercase tracking-wider text-muted">
          <span>Konfidenz</span>
          <span className="font-mono normal-case tracking-normal text-secondary">{confidence}%</span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
          <div className="h-full rounded-full bg-accent" style={{ width: `${confidence}%` }} />
        </div>
      </div>

      <div className="flex flex-wrap gap-2 text-xs">
        <Badge tone="accent">{result.latency_ms < 1 ? "< 1 ms" : `${result.latency_ms} ms`}</Badge>
        <Badge>{result.engine}</Badge>
        {result.degraded && <Badge tone="warning">Fallback aktiv</Badge>}
        {piiEntries.length > 0 ? (
          <Badge tone="good">
            DSGVO: {piiEntries.map(([kind, count]) => `${count}× ${kind}`).join(", ")} anonymisiert
          </Badge>
        ) : (
          <Badge>Keine personenbezogenen Daten gefunden</Badge>
        )}
      </div>
    </div>
  );
}

/** Minimaler JSON-Highlighter ohne Abhängigkeiten. */
export function JsonView({ value }: { value: unknown }) {
  const json = JSON.stringify(value, null, 2);
  const parts = json.split(/("(?:\\.|[^"\\])*"(?:\s*:)?|\btrue\b|\bfalse\b|\bnull\b|-?\d+(?:\.\d+)?)/g);
  return (
    <pre className="overflow-x-auto font-mono text-[12.5px] leading-relaxed text-secondary">
      <code>
        {parts.map((part, index) => {
          if (!part) return null;
          let color = "";
          if (/^".*":$/.test(part.replace(/\s+/g, ""))) color = "text-accent-strong";
          else if (part.startsWith('"')) color = "text-[#7ee2b8]";
          else if (part === "true" || part === "false" || part === "null") color = "text-[#f2a96b]";
          else if (/^-?\d/.test(part)) color = "text-[#79b8ff]";
          return (
            <span key={index} className={color}>
              {part}
            </span>
          );
        })}
      </code>
    </pre>
  );
}
