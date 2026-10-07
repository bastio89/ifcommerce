import { Building2, Gauge, Layers, Plug, Receipt, Scale } from "lucide-react";

import { SectionHeading } from "@/components/marketing/section-heading";

const features = [
  {
    icon: Layers,
    title: "Fünf E-Commerce-Kategorien",
    text: "WHERE_IS_MY_ORDER, RETURN_OR_REFUND, PRODUCT_ISSUE, PAYMENT_OR_INVOICE und GENERAL_INQUIRY im festen API-Schema.",
  },
  {
    icon: Gauge,
    title: "Dringlichkeit 1–5",
    text: "Von der Produktfrage bis zur Anwaltsdrohung. Kritische Tickets landen sofort oben, statt im Posteingang zu altern.",
  },
  {
    icon: Scale,
    title: "Intent-Flags & Konfidenz",
    text: "is_cancellation_request und contains_order_number als harte Booleans, plus eine Konfidenz für deine Schwellenwerte.",
  },
  {
    icon: Plug,
    title: "Widget und REST-API",
    text: "Das Widget bindet Standard-HTML-Formulare an. Helpdesks lassen sich über ihre REST- oder Automationsfunktionen integrieren; native Connectoren sind nicht enthalten.",
  },
  {
    icon: Building2,
    title: "Mandantenfähig ab Tag 1",
    text: "Gehashte API-Keys pro Shop, Publishable Keys mit Domain-Allowlist, Rate-Limits und vollständiges Usage-Logging.",
  },
  {
    icon: Receipt,
    title: "Faire Abrechnung",
    text: "Starte kostenlos. Pro kostet eine feste Grundgebühr plus Nutzung, abgerechnet über Stripe. Keine Token-Rechnerei.",
  },
];

export function Features() {
  return (
    <section className="border-y border-border bg-surface/40">
      <div className="mx-auto max-w-6xl px-4 py-24 sm:px-6">
        <SectionHeading
          eyebrow="Features"
          title="Alles, was ein Support-Router braucht"
          description="Gebaut für Händler, die schneller antworten wollen, ohne ein KI-Team einzustellen."
        />
        <div className="grid grid-cols-1 gap-px overflow-hidden rounded-2xl border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">
          {features.map(({ icon: Icon, title, text }) => (
            <div key={title} className="bg-background p-6">
              <Icon className="mb-4 size-5 text-accent-strong" aria-hidden />
              <h3 className="mb-2 font-semibold">{title}</h3>
              <p className="text-[14px] leading-relaxed text-secondary">{text}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
