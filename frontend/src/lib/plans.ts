/**
 * Tarifmodell – eine Quelle für Pricing-Seite und Billing-Dashboard.
 * Die tatsächlichen Preise/Staffeln liegen in Stripe (siehe README "Stripe einrichten").
 */
export const PRO_MONTHLY_PRICE_USD = 49;
export const PRO_INCLUDED_ANALYSES = 10_000;
export const PRO_OVERAGE_PER_ANALYSIS_USD = 0.002;

export const PLAN_FEATURES = {
  FREE: [
    "Bis zu {limit} Analysen pro Monat",
    "Alle 5 Kategorien, Dringlichkeit & Intent-Flags",
    "DSGVO-Schutzschicht (PII-Anonymisierung)",
    "JavaScript-Widget & REST-API",
    "Community-Support",
  ],
  PRO: [
    `${PRO_INCLUDED_ANALYSES.toLocaleString("de-DE")} Analysen inklusive`,
    `danach ${PRO_OVERAGE_PER_ANALYSIS_USD.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 3 })} pro Analyse`,
    "Unbegrenzte API-Keys & Publishable Keys",
    "Höhere Rate-Limits für Helpdesk-Integrationen",
    "Verbrauchsbasierte Abrechnung über Stripe",
    "Priorisierter E-Mail-Support",
  ],
} as const;

export function freeFeatures(limit: number): string[] {
  return PLAN_FEATURES.FREE.map((feature) => feature.replace("{limit}", limit.toLocaleString("de-DE")));
}
