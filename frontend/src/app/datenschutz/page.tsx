import type { Metadata } from "next";

import { LegalLayout } from "@/app/legal-layout";

export const metadata: Metadata = { title: "Datenschutz" };

// VORLAGE: Technische Fakten zur Datenverarbeitung; die rechtliche Erklärung muss
// vom Betreiber (ggf. mit Rechtsberatung) vervollständigt werden.
export default function DatenschutzPage() {
  return (
    <LegalLayout title="Datenschutz">
      <p className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
        Platzhalter: Diese Seite beschreibt die technische Verarbeitung. Die vollständige Datenschutzerklärung muss
        vom Betreiber ergänzt werden.
      </p>
      <h2>Verarbeitung von Support-Nachrichten</h2>
      <p>
        Über die API übermittelte Texte werden ausschließlich zur Klassifikation verarbeitet. Vor jeder Übergabe an ein
        KI-Modell entfernt eine lokale Schutzschicht E-Mail-Adressen, Telefonnummern, Namen, Adressen, IBANs,
        Kartennummern und IP-Adressen.
      </p>
      <h2>Gespeicherte Daten</h2>
      <p>
        Pro Analyse werden nur Metadaten gespeichert (Zeitpunkt, Kategorie, Dringlichkeit, Latenz, verwendete Engine).
        Ticket-Inhalte werden nicht gespeichert.
      </p>
      <h2>Auftragsverarbeiter</h2>
      <p>[KI-Anbieter, Hosting-Anbieter, Stripe als Zahlungsdienstleister – bitte mit AV-Verträgen ergänzen.]</p>
    </LegalLayout>
  );
}
