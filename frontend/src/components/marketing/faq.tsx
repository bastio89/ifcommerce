import { SectionHeading } from "@/components/marketing/section-heading";

const faqs = [
  {
    q: "Was ist ein Decision-Modell?",
    a: "Statt eine Antwort zu formulieren, trifft das Modell nur eine strukturierte Entscheidung in einem festen Schema. Das ist schneller, günstiger und für Automationen verlässlicher als frei generierter Text.",
  },
  {
    q: "Wie werden personenbezogene Daten behandelt?",
    a: "Vor dem Modellaufruf versucht eine lokale Schutzschicht ausgewählte Muster zu maskieren. Sie erkennt nicht jede personenbezogene Angabe; die Inhalte können daher weiterhin personenbezogen sein. Analysejobs und Ergebnisse einschließlich maskiertem Text werden standardmäßig bis zu sieben Tage gespeichert. Die Angaben ersetzen keine Datenschutzprüfung.",
  },
  {
    q: "Was passiert, wenn die KI ausfällt?",
    a: "Dann übernimmt automatisch eine deterministische Regel-Engine. Die Antwort enthält dann degraded: true, dein Formular und dein Helpdesk laufen weiter.",
  },
  {
    q: "Funktioniert das mit meinem Shopsystem?",
    a: "Das Widget ist für Standard-HTML-Kontaktformulare gedacht. Für Helpdesks wie Zendesk oder Freshdesk gibt es eine REST-API, aber keinen nativen Connector; die konkrete Automation muss im Helpdesk eingerichtet werden.",
  },
  {
    q: "Wie wird abgerechnet?",
    a: "Free ist kostenlos bis zum Monatskontingent. Pro kostet eine feste Grundgebühr plus einen Betrag pro abrechenbarer Analyse oberhalb des Inklusivvolumens. Ergebnisse mit Heuristik-Fallback (degraded) werden nicht nutzungsbasiert abgerechnet.",
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
