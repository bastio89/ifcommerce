import { ArrowRight } from "lucide-react";

import { CategoryBreakdown } from "@/components/dashboard/category-breakdown";
import { PageHeader } from "@/components/dashboard/page-header";
import { QuotaMeter, StatTile } from "@/components/dashboard/stat-tile";
import { UsageChart } from "@/components/dashboard/usage-chart";
import { ButtonLink } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { env } from "@/lib/env";
import { PRO_INCLUDED_ANALYSES } from "@/lib/plans";
import { getUsageOverview } from "@/lib/usage";
import { formatNumber } from "@/lib/utils";

function deltaText(current: number, previous: number): string {
  if (previous === 0) return current > 0 ? "Erster Monat mit Analysen" : "Noch keine Analysen";
  const change = Math.round(((current - previous) / previous) * 100);
  return `${change > 0 ? "+" : ""}${change} % ggü. Vormonat`;
}

export default async function OverviewPage() {
  const user = await requireUser();
  const [usage, activeKeys] = await Promise.all([
    getUsageOverview(user.tenantId),
    db().apiKey.count({ where: { tenantId: user.tenantId, revokedAt: null } }),
  ]);
  const isPro = user.tenant.plan === "PRO";
  const limit = env().FREE_TIER_MONTHLY_LIMIT;
  const urgentShare = usage.totalThisMonth > 0 ? Math.round((usage.urgentCount / usage.totalThisMonth) * 100) : 0;

  return (
    <>
      <PageHeader title="Übersicht" description={`Nutzung für ${usage.monthLabel} (UTC)`} />

      {activeKeys === 0 && (
        <Card className="mb-6 border-accent/40 bg-accent/[0.06]">
          <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="font-medium">Erzeuge deinen ersten API-Key</div>
              <div className="text-sm text-secondary">Danach kannst du Tickets per Widget oder REST-API analysieren.</div>
            </div>
            <ButtonLink href="/dashboard/keys" variant="accent" size="sm">
              API-Key erstellen <ArrowRight className="size-4" aria-hidden />
            </ButtonLink>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Analysen diesen Monat"
          value={formatNumber(usage.totalThisMonth)}
          detail={deltaText(usage.totalThisMonth, usage.totalPreviousMonth)}
        />
        {isPro ? (
          <StatTile
            label="Inklusivvolumen Pro"
            value={formatNumber(Math.max(PRO_INCLUDED_ANALYSES - usage.totalThisMonth, 0))}
            detail={`von ${formatNumber(PRO_INCLUDED_ANALYSES)} übrig, danach nutzungsbasiert`}
          >
            <QuotaMeter used={usage.totalThisMonth} limit={PRO_INCLUDED_ANALYSES} />
          </StatTile>
        ) : (
          <StatTile
            label="Verbleibendes Kontingent"
            value={formatNumber(Math.max(limit - usage.totalThisMonth, 0))}
            detail={`von ${formatNumber(limit)} Analysen im Free-Tarif`}
          >
            <QuotaMeter used={usage.totalThisMonth} limit={limit} />
          </StatTile>
        )}
        <StatTile
          label="Ø Antwortzeit"
          value={usage.avgLatencyMs === null ? "–" : usage.avgLatencyMs < 1 ? "< 1 ms" : `${formatNumber(usage.avgLatencyMs)} ms`}
          detail="inkl. Anonymisierung & Entscheidung"
        />
        <StatTile
          label="Dringende Tickets"
          value={formatNumber(usage.urgentCount)}
          detail={`${urgentShare} % mit Dringlichkeit ≥ 4`}
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Analysierte Tickets pro Tag</CardTitle>
            <CardDescription>Erfolgreiche Analysen im {usage.monthLabel}</CardDescription>
          </CardHeader>
          <CardContent>
            <UsageChart data={usage.daily} />
            <details className="mt-3 text-[13px]">
              <summary className="cursor-pointer text-muted hover:text-foreground">Als Tabelle anzeigen</summary>
              <table className="mt-3 w-full text-left tabular-nums">
                <thead className="text-muted">
                  <tr>
                    <th className="py-1 font-normal">Datum</th>
                    <th className="py-1 text-right font-normal">Analysen</th>
                  </tr>
                </thead>
                <tbody>
                  {usage.daily
                    .filter((point) => point.count > 0)
                    .map((point) => (
                      <tr key={point.date} className="border-t border-border">
                        <td className="py-1 text-secondary">{point.date}</td>
                        <td className="py-1 text-right">{formatNumber(point.count)}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </details>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Nach Kategorie</CardTitle>
            <CardDescription>Verteilung der Anliegen in diesem Monat</CardDescription>
          </CardHeader>
          <CardContent>
            <CategoryBreakdown categories={usage.categories} />
          </CardContent>
        </Card>
      </div>
    </>
  );
}
