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
        Vor einem Modellaufruf versucht eine lokale Schutzschicht ausgewählte Muster wie E-Mail-Adressen,
        Telefonnummern, Namen, Adressen, IBANs, Kartennummern und IP-Adressen zu maskieren. Die Erkennung ist
        heuristisch und nicht vollständig. Maskierte Texte können weiterhin personenbezogene Daten enthalten; die
        Verarbeitung ist daher nicht als garantierte Anonymisierung zu verstehen.
      </p>
      <h2>Gespeicherte Daten</h2>
      <p>
        Analyseaufträge speichern den vor dem Einreihen maskierten Text und nach Abschluss das Ergebnis einschließlich
        der maskierten Textfassung. Aufträge und Ergebnisse werden standardmäßig nach sieben Tagen gelöscht. Die
        Aufbewahrungsdauer ist konfigurierbar. Abrechnungs- und Nutzungslogs enthalten zusätzlich Metadaten wie
        Zeitpunkt, Kategorie, Dringlichkeit, Latenz und verwendete Engine.
      </p>
      <h2>Auftragsverarbeiter</h2>
      <p>[KI-Anbieter, Hosting-Anbieter, Stripe als Zahlungsdienstleister – bitte mit AV-Verträgen ergänzen.]</p>
    </LegalLayout>
  );
}
