import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { Metadata } from "next";

import { BillingAction } from "@/components/dashboard/billing-actions";
import { PageHeader } from "@/components/dashboard/page-header";
import { PlanBadge } from "@/components/dashboard/plan-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { env, stripeConfigured } from "@/lib/env";
import {
  PLAN_FEATURES,
  PRO_INCLUDED_ANALYSES,
  PRO_MONTHLY_PRICE_USD,
  PRO_OVERAGE_PER_ANALYSIS_USD,
  freeFeatures,
} from "@/lib/plans";
import { formatNumber } from "@/lib/utils";

export const metadata: Metadata = { title: "Abrechnung" };

const dateFormat = new Intl.DateTimeFormat("de-DE", { dateStyle: "long", timeZone: "UTC" });

export default async function BillingPage({ searchParams }: PageProps<"/dashboard/billing">) {
  const user = await requireUser();
  const { checkout } = await searchParams;
  const tenant = user.tenant;
  const billingReady = stripeConfigured();
  const freeLimit = env().FREE_TIER_MONTHLY_LIMIT;

  const monthStart = new Date(Date.UTC(new Date().getUTCFullYear(), new Date().getUTCMonth(), 1));
  const [usedThisMonth, billableThisMonth] = await Promise.all([
    db().usageLog.count({ where: { tenantId: tenant.id, timestamp: { gte: monthStart } } }),
    db().usageLog.count({ where: { tenantId: tenant.id, timestamp: { gte: monthStart }, billable: true } }),
  ]);

  const isPro = tenant.plan === "PRO";
  const hasActiveSubscription = isPro && ["ACTIVE", "TRIALING", "PAST_DUE"].includes(tenant.subscriptionStatus);
  const overage = Math.max(billableThisMonth - PRO_INCLUDED_ANALYSES, 0);
  const estimatedTotal = PRO_MONTHLY_PRICE_USD + overage * PRO_OVERAGE_PER_ANALYSIS_USD;

  return (
    <>
      <PageHeader title="Abrechnung" description="Tarif, Verbrauch und Zahlungsdaten deines Shops." />

      {checkout === "success" && (
        <div className="mb-6 flex items-start gap-3 rounded-xl border border-good/40 bg-good/[0.07] p-4 text-sm">
          <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-good" aria-hidden />
          <div>
            <div className="font-medium">Danke für dein Upgrade!</div>
            <div className="text-secondary">
              Sobald Stripe die Zahlung bestätigt, wird dein Shop automatisch auf Pro umgestellt. Das dauert meist nur
              wenige Sekunden.
            </div>
          </div>
        </div>
      )}

      {isPro && (tenant.subscriptionStatus === "PAST_DUE" || tenant.subscriptionStatus === "UNPAID") && (
        <div className="mb-6 flex items-start gap-3 rounded-xl border border-warning/40 bg-warning/[0.07] p-4 text-sm">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
          <div>
            <div className="font-medium">Zahlung fehlgeschlagen</div>
            <div className="text-secondary">
              {tenant.subscriptionStatus === "UNPAID"
                ? "Die API ist gesperrt, bis die offene Rechnung beglichen ist."
                : "Bitte aktualisiere deine Zahlungsmethode, um eine Sperrung zu vermeiden."}
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <CardTitle>Aktueller Tarif</CardTitle>
              <PlanBadge plan={tenant.plan} status={tenant.subscriptionStatus} />
            </div>
            <CardDescription>
              {isPro
                ? `$${PRO_MONTHLY_PRICE_USD}/Monat inkl. ${formatNumber(PRO_INCLUDED_ANALYSES)} Analysen, danach nutzungsbasiert.`
                : `Kostenlos bis ${formatNumber(freeLimit)} Analysen pro Monat.`}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            <ul className="flex flex-col gap-2 text-sm text-secondary">
              {(isPro ? [...PLAN_FEATURES.PRO] : freeFeatures(freeLimit)).map((feature) => (
                <li key={feature}>· {feature}</li>
              ))}
            </ul>
            {tenant.subscriptionCurrentPeriodEnd && hasActiveSubscription && (
              <p className="text-sm text-muted">
                Nächste Abrechnung: {dateFormat.format(tenant.subscriptionCurrentPeriodEnd)}
              </p>
            )}
            {!billingReady ? (
              <p className="rounded-lg border border-border-strong bg-background p-3 text-sm text-muted">
                Billing ist in dieser Umgebung noch nicht konfiguriert (STRIPE_SECRET_KEY, STRIPE_PRICE_PRO_BASE,
                STRIPE_PRICE_PRO_METERED).
              </p>
            ) : hasActiveSubscription || tenant.stripeCustomerId ? (
              <div className="flex flex-wrap gap-3">
                {!hasActiveSubscription && <BillingAction action="checkout" label="Auf Pro upgraden" />}
                <BillingAction action="portal" label="Zahlungen & Rechnungen verwalten" />
              </div>
            ) : (
              <BillingAction action="checkout" label="Auf Pro upgraden" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Verbrauch diesen Monat</CardTitle>
            <CardDescription>Gezählt werden nur erfolgreiche Analysen.</CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-4">
              <div>
                <dt className="text-[13px] text-muted">Analysen gesamt</dt>
                <dd className="mt-1 text-2xl font-semibold">{formatNumber(usedThisMonth)}</dd>
              </div>
              <div>
                <dt className="text-[13px] text-muted">{isPro ? "Davon über Inklusivvolumen" : "Free-Kontingent"}</dt>
                <dd className="mt-1 text-2xl font-semibold">
                  {isPro ? formatNumber(overage) : `${formatNumber(Math.min(usedThisMonth, freeLimit))} / ${formatNumber(freeLimit)}`}
                </dd>
              </div>
              {isPro && (
                <div className="col-span-2 rounded-lg border border-border bg-background p-3">
                  <dt className="text-[13px] text-muted">Voraussichtliche Rechnung (netto)</dt>
                  <dd className="mt-1 text-lg font-semibold">
                    {estimatedTotal.toLocaleString("en-US", { style: "currency", currency: "USD" })}
                  </dd>
                </div>
              )}
            </dl>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
