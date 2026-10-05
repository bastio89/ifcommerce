"use client";

import { Braces, LayoutPanelLeft, Loader2, Play, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { DecisionSummary, JsonView } from "@/components/decision-view";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import type { AnalyzeResult, ApiError } from "@/lib/types";
import { cn } from "@/lib/utils";

const EXAMPLES = [
  {
    label: "Wütender Kunde",
    text: "Seit DREI Wochen warte ich auf meine Bestellung 4711-2025!!! Niemand antwortet. Wenn das Paket nicht bis Freitag da ist, schalte ich meinen Anwalt ein.\n\nMax Mustermann\nTel. 0171 1234567",
  },
  {
    label: "Storno",
    text: "Hallo, ich habe gestern aus Versehen zweimal bestellt (Bestellnummer #10234). Bitte storniert die zweite Bestellung sofort, bevor sie verschickt wird. Danke, Anna Schmidt",
  },
  {
    label: "Retoure",
    text: "Hi, the sneakers are too small. How can I return them and get a refund? My email is jane.doe@example.com",
  },
  {
    label: "Rechnung",
    text: "Guten Tag, mir wurde der Betrag für Auftrag ORD-889911 doppelt per PayPal abgebucht. Könnten Sie das bitte prüfen und mir eine korrigierte Rechnung schicken?",
  },
  {
    label: "Produktfrage",
    text: "Hallo zusammen, ist die Regenjacke in Größe M bald wieder auf Lager? Und ist sie auch für Radtouren geeignet?",
  },
];

type View = "visual" | "json";

export function LiveDemo() {
  const [text, setText] = useState(EXAMPLES[0]!.text);
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<View>("visual");

  async function analyze() {
    if (loading || text.trim().length < 3) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/demo", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const body = (await response.json()) as AnalyzeResult | ApiError;
      if (!response.ok || "error" in body) {
        setError("error" in body ? body.error.message : "Analyse fehlgeschlagen.");
        return;
      }
      setResult(body);
    } catch {
      setError("Netzwerkfehler – bitte erneut versuchen.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div className="flex flex-col rounded-2xl border border-border bg-surface p-4 sm:p-5">
        <div className="mb-3 flex flex-wrap gap-2">
          {EXAMPLES.map((example) => (
            <button
              key={example.label}
              type="button"
              onClick={() => {
                setText(example.text);
                setResult(null);
              }}
              className={cn(
                "rounded-full border px-3 py-1 text-xs transition-colors",
                text === example.text
                  ? "border-accent/50 bg-accent/10 text-accent-strong"
                  : "border-border-strong text-muted hover:text-foreground",
              )}
            >
              {example.label}
            </button>
          ))}
        </div>
        <label htmlFor="demo-text" className="sr-only">
          Test-Nachricht
        </label>
        <Textarea
          id="demo-text"
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if ((event.metaKey || event.ctrlKey) && event.key === "Enter") void analyze();
          }}
          rows={9}
          maxLength={2000}
          placeholder="Füge eine echte Kunden-E-Mail ein …"
          className="min-h-56 flex-1 resize-none font-mono text-[13px]"
        />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <span className="flex items-center gap-1.5 text-xs text-muted">
            <ShieldCheck className="size-3.5 text-good" aria-hidden />
            Namen, E-Mails und Telefonnummern werden vor der KI anonymisiert.
          </span>
          <Button onClick={analyze} disabled={loading || text.trim().length < 3} variant="accent">
            {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Play className="size-4" aria-hidden />}
            Analysieren
            <kbd className="hidden rounded border border-white/20 px-1 font-mono text-[10px] text-white/70 sm:inline">
              ⌘↵
            </kbd>
          </Button>
        </div>
      </div>

      <div className="flex min-h-[420px] flex-col rounded-2xl border border-border bg-surface">
        <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
          <span className="text-[13px] font-medium text-secondary">Entscheidung</span>
          <div className="flex rounded-lg border border-border bg-background p-0.5" role="tablist" aria-label="Ansicht">
            {(
              [
                { id: "visual", label: "Visuell", icon: LayoutPanelLeft },
                { id: "json", label: "JSON", icon: Braces },
              ] as const
            ).map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={view === id}
                onClick={() => setView(id)}
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs transition-colors",
                  view === id ? "bg-surface-3 text-foreground" : "text-muted hover:text-foreground",
                )}
              >
                <Icon className="size-3.5" aria-hidden />
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className={cn("flex-1 p-5 transition-opacity", loading && result && "opacity-50")} aria-live="polite">
          {error && (
            <div className="rounded-lg border border-critical/40 bg-critical/10 px-3 py-2 text-sm text-critical">{error}</div>
          )}
          {!error && !result && (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-sm text-muted">
              <Braces className="size-6" aria-hidden />
              Wähle ein Beispiel oder füge eine eigene Nachricht ein und klicke auf „Analysieren“.
            </div>
          )}
          {!error && result && view === "visual" && (
            <div className="flex flex-col gap-5">
              <DecisionSummary result={result} />
              <div>
                <div className="mb-1.5 text-xs uppercase tracking-wider text-muted">Was das Modell gesehen hat</div>
                <p className="max-h-32 overflow-y-auto rounded-lg border border-border bg-background p-3 font-mono text-[12px] leading-relaxed whitespace-pre-wrap text-secondary">
                  {result.anonymized_text}
                </p>
              </div>
            </div>
          )}
          {!error && result && view === "json" && <JsonView value={result} />}
        </div>
      </div>
    </div>
  );
}
