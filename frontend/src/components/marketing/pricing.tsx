import { Check } from "lucide-react";

import { SectionHeading } from "@/components/marketing/section-heading";
import { ButtonLink } from "@/components/ui/button";
import { PLAN_FEATURES, PRO_MONTHLY_PRICE_USD, freeFeatures } from "@/lib/plans";
import { cn } from "@/lib/utils";

export function Pricing({ freeLimit }: { freeLimit: number }) {
  const plans = [
    {
      name: "Free",
      price: "$0",
      period: "für immer",
      description: "Zum Testen und für kleine Shops.",
      features: freeFeatures(freeLimit),
      cta: "Kostenlos starten",
      highlighted: false,
    },
    {
      name: "Pro",
      price: `$${PRO_MONTHLY_PRICE_USD}`,
      period: "pro Monat + Nutzung",
      description: "Für wachsende Shops mit echtem Ticketvolumen.",
      features: [...PLAN_FEATURES.PRO],
      cta: "Mit Pro starten",
      highlighted: true,
    },
  ];

  return (
    <section id="preise" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-24 sm:px-6">
      <SectionHeading
        eyebrow="Preise"
        title="Einfach. Transparent. Usage-based."
        description="Bezahle für Entscheidungen, nicht für Tokens. Monatlich kündbar, Abrechnung über Stripe."
      />
      <div className="mx-auto grid max-w-4xl grid-cols-1 gap-4 md:grid-cols-2">
        {plans.map((plan) => (
          <div
            key={plan.name}
            className={cn(
              "relative flex flex-col rounded-2xl border p-7",
              plan.highlighted ? "border-accent/50 bg-surface shadow-[0_0_80px_-20px_rgb(124_108_240/0.45)]" : "border-border bg-surface/60",
            )}
          >
            {plan.highlighted && (
              <span className="absolute -top-3 left-7 rounded-full border border-accent/50 bg-background px-3 py-0.5 text-xs text-accent-strong">
                Beliebt
              </span>
            )}
            <h3 className="text-lg font-semibold">{plan.name}</h3>
            <p className="mt-1 text-sm text-muted">{plan.description}</p>
            <div className="mt-6 flex items-baseline gap-2">
              <span className="text-4xl font-semibold tracking-tight">{plan.price}</span>
              <span className="text-sm text-muted">{plan.period}</span>
            </div>
            <ul className="mt-6 flex flex-1 flex-col gap-3">
              {plan.features.map((feature) => (
                <li key={feature} className="flex items-start gap-2.5 text-[14px] text-secondary">
                  <Check className="mt-0.5 size-4 shrink-0 text-accent-strong" aria-hidden />
                  {feature}
                </li>
              ))}
            </ul>
            <ButtonLink
              href={plan.highlighted ? "/signup?plan=pro" : "/signup"}
              variant={plan.highlighted ? "accent" : "secondary"}
              className="mt-8 w-full"
            >
              {plan.cta}
            </ButtonLink>
          </div>
        ))}
      </div>
      <p className="mt-8 text-center text-[13px] text-muted">
        Größeres Volumen oder individuelle Integration? Sprich mit uns über einen passenden Pilotumfang.
      </p>
    </section>
  );
}
