import { Braces, GitBranch, ShieldCheck } from "lucide-react";

import { SectionHeading } from "@/components/marketing/section-heading";

const steps = [
  {
    icon: ShieldCheck,
    title: "1 · Anonymisieren",
    text: "Eine lokale Schutzschicht ersetzt E-Mails, Telefonnummern, Klarnamen, Adressen, IBANs und Kartennummern durch Platzhalter wie [ANONYMOUS_EMAIL], bevor irgendetwas die KI erreicht. Bestellnummern bleiben erhalten.",
  },
  {
    icon: Braces,
    title: "2 · Entscheiden",
    text: "Das Decision-Modell presst das Ticket in einem einzigen Durchlauf in ein festes Schema: Kategorie, Dringlichkeit 1–5, Intent-Flags und Konfidenz. Kein Fließtext, kein Parsing, keine Halluzinationen im Format.",
  },
  {
    icon: GitBranch,
    title: "3 · Handeln",
    text: "Dein Helpdesk, Shop-Backend oder Kontaktformular verzweigt mit simplen If-Statements: Storno stoppen, Eskalationen priorisieren, Standardfälle automatisch beantworten.",
  },
];

export function HowItWorks() {
  return (
    <section id="so-funktionierts" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-24 sm:px-6">
      <SectionHeading
        eyebrow="So funktioniert's"
        title="Von der Wut-Mail zur Routing-Entscheidung"
        description="System-1-Denken für deinen Support: schnell, deterministisch im Format und abrechenbar pro Entscheidung."
      />
      <ol className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {steps.map(({ icon: Icon, title, text }) => (
          <li key={title} className="rounded-2xl border border-border bg-surface p-6">
            <div className="mb-5 flex size-10 items-center justify-center rounded-lg border border-border-strong bg-surface-2">
              <Icon className="size-5 text-accent-strong" aria-hidden />
            </div>
            <h3 className="mb-2 font-semibold">{title}</h3>
            <p className="text-[14px] leading-relaxed text-secondary">{text}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
