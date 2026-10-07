import { ArrowRight, ShieldCheck, Sparkles, Zap } from "lucide-react";

import { ButtonLink } from "@/components/ui/button";

const decisionCode = `const decision = await decide(ticket);

if (decision.flags.is_cancellation_request) {
  holdShipment(order);          // vor dem Versand stoppen
}
if (decision.urgency >= 4) {
  routeTo("senior-support");    // Eskalation in Sekunden
}
if (decision.category === "WHERE_IS_MY_ORDER") {
  replyWithTracking(order);     // Standardfall automatisieren
}`;

export function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div className="bg-grid pointer-events-none absolute inset-0" aria-hidden />
      <div className="glow pointer-events-none absolute inset-x-0 top-0 h-[520px]" aria-hidden />

      <div className="relative mx-auto grid max-w-6xl grid-cols-1 gap-14 px-4 pt-20 pb-16 sm:px-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] lg:items-center lg:pt-28">
        <div>
          <a
            href="#demo"
            className="mb-6 inline-flex items-center gap-2 rounded-full border border-border-strong bg-surface/80 px-3 py-1 text-xs text-secondary transition-colors hover:text-foreground"
          >
            <Sparkles className="size-3.5 text-accent-strong" aria-hidden />
            Decision-Modelle statt Textgenerierung
            <ArrowRight className="size-3.5" aria-hidden />
          </a>
          <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-5xl lg:text-[3.5rem] lg:leading-[1.05]">
            <span className="text-gradient">Strukturierte Triage für E-Commerce-Support.</span>
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-secondary">
            DecideCommerce liest Support-Nachrichten und liefert eine strukturierte Einschätzung: Kategorie,
            Dringlichkeit, Storno-Wunsch und Bestellnummer. Erkannte personenbezogene Daten werden vor dem Modellaufruf
            lokal maskiert; eine vollständige Erkennung kann nicht garantiert werden.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <ButtonLink href="/signup" size="lg">
              Jetzt kostenlos starten
              <ArrowRight className="size-4" aria-hidden />
            </ButtonLink>
            <ButtonLink href="#demo" variant="secondary" size="lg">
              Live-Demo testen
            </ButtonLink>
          </div>
          <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-[13px] text-muted">
            <li className="flex items-center gap-2">
              <ShieldCheck className="size-4 text-good" aria-hidden /> Erkannte PII-Muster werden lokal maskiert
            </li>
            <li className="flex items-center gap-2">
              <Zap className="size-4 text-accent-strong" aria-hidden /> Ein API-Call, ein Entscheidungsobjekt
            </li>
          </ul>
        </div>

        <div className="relative">
          <div className="absolute -inset-6 rounded-3xl bg-accent/10 blur-3xl" aria-hidden />
          <div className="relative overflow-hidden rounded-2xl border border-border-strong bg-surface shadow-2xl shadow-black/50">
            <div className="flex items-center gap-2 border-b border-border px-4 py-3">
              <span className="size-2.5 rounded-full bg-white/15" />
              <span className="size-2.5 rounded-full bg-white/15" />
              <span className="size-2.5 rounded-full bg-white/15" />
              <span className="ml-2 font-mono text-xs text-muted">support-router.ts</span>
            </div>
            <pre className="overflow-x-auto p-5 font-mono text-[12.5px] leading-relaxed text-secondary">
              <code>{decisionCode}</code>
            </pre>
          </div>
        </div>
      </div>
    </section>
  );
}
