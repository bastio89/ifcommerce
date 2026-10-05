import { SectionHeading } from "@/components/marketing/section-heading";

const faqs = [
  {
    q: "Was ist ein Decision-Modell?",
    a: "Statt eine Antwort zu formulieren, trifft das Modell nur eine strukturierte Entscheidung in einem festen Schema. Das ist schneller, günstiger und für Automationen verlässlicher als frei generierter Text.",
  },
  {
    q: "Ist das DSGVO-konform?",
    a: "Personenbezogene Daten (E-Mails, Telefonnummern, Namen, Adressen, IBANs, Kartennummern, IPs) werden lokal anonymisiert, bevor der Text an ein KI-Modell geht. Die Analyse-Logs enthalten nur Metadaten wie Kategorie und Dringlichkeit, keine Ticket-Inhalte.",
  },
  {
    q: "Was passiert, wenn die KI ausfällt?",
    a: "Dann übernimmt automatisch eine deterministische Regel-Engine. Die Antwort enthält dann degraded: true, dein Formular und dein Helpdesk laufen weiter.",
  },
  {
    q: "Funktioniert das mit meinem Shopsystem?",
    a: "Das Widget arbeitet mit jedem HTML-Kontaktformular (Shopify, Shopware, WooCommerce, Magento, JTL, eigene Shops). Helpdesks wie Zendesk oder Freshdesk binden die REST-API per Webhook oder Automation an.",
  },
  {
    q: "Wie wird abgerechnet?",
    a: "Free ist kostenlos bis zum Monatskontingent. Pro kostet eine feste Grundgebühr plus einen Betrag pro Analyse oberhalb des Inklusivvolumens. Gezählt werden nur erfolgreiche Analysen, abgerechnet monatlich über Stripe.",
  },
];

export function Faq() {
  return (
    <section id="faq" className="mx-auto max-w-3xl scroll-mt-20 px-4 py-24 sm:px-6">
      <SectionHeading eyebrow="FAQ" title="Häufige Fragen" />
      <div className="divide-y divide-border rounded-2xl border border-border bg-surface">
        {faqs.map(({ q, a }) => (
          <details key={q} className="group px-6 py-5 [&_summary::-webkit-details-marker]:hidden">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium">
              {q}
              <span className="text-muted transition-transform group-open:rotate-45" aria-hidden>
                +
              </span>
            </summary>
            <p className="mt-3 text-[14px] leading-relaxed text-secondary">{a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
