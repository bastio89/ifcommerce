import type { Metadata } from "next";

import { LegalLayout } from "@/app/legal-layout";

export const metadata: Metadata = { title: "Impressum" };

// VORLAGE: Vor dem Livegang mit den echten Angaben des Betreibers ersetzen (§ 5 DDG).
export default function ImpressumPage() {
  return (
    <LegalLayout title="Impressum">
      <p className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
        Platzhalter: Bitte vor dem Livegang durch die Angaben des Betreibers ersetzen.
      </p>
      <h2>Angaben gemäß § 5 DDG</h2>
      <p>
        [Firmenname]
        <br />
        [Straße Hausnummer]
        <br />
        [PLZ Ort]
      </p>
      <h2>Kontakt</h2>
      <p>E-Mail: [kontakt@deine-domain.de]</p>
      <h2>Vertreten durch</h2>
      <p>[Geschäftsführung]</p>
      <h2>Registereintrag & USt-IdNr.</h2>
      <p>[Registergericht, Registernummer, USt-IdNr.]</p>
    </LegalLayout>
  );
}
