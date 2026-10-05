import type { TicketCategory } from "@/generated/prisma/enums";
import { db } from "@/lib/db";

export const CATEGORY_LABELS: Record<TicketCategory, string> = {
  WHERE_IS_MY_ORDER: "Wo ist meine Bestellung?",
  RETURN_OR_REFUND: "Retoure / Erstattung",
  PRODUCT_ISSUE: "Produktproblem",
  PAYMENT_OR_INVOICE: "Zahlung / Rechnung",
  GENERAL_INQUIRY: "Allgemeine Anfrage",
};

export type DailyPoint = { date: string; day: number; count: number };

export type UsageOverview = {
  monthLabel: string;
  totalThisMonth: number;
  totalPreviousMonth: number;
  daily: DailyPoint[];
  categories: { category: TicketCategory; label: string; count: number }[];
  avgLatencyMs: number | null;
  urgentCount: number;
};

function monthStartUtc(offsetMonths = 0): Date {
  const now = new Date();
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + offsetMonths, 1));
}

export async function getUsageOverview(tenantId: string): Promise<UsageOverview> {
  const start = monthStartUtc(0);
  const nextStart = monthStartUtc(1);
  const previousStart = monthStartUtc(-1);
  const thisMonth = { tenantId, timestamp: { gte: start, lt: nextStart } };

  const [dailyRows, byCategory, aggregate, previous, urgent] = await Promise.all([
    db().$queryRaw<{ day: number; count: number }[]>`
      SELECT EXTRACT(DAY FROM "timestamp" AT TIME ZONE 'UTC')::int AS day, count(*)::int AS count
      FROM usage_logs
      WHERE tenant_id = ${tenantId}::uuid AND "timestamp" >= ${start} AND "timestamp" < ${nextStart}
      GROUP BY 1
      ORDER BY 1`,
    db().usageLog.groupBy({ by: ["category"], where: thisMonth, _count: { _all: true } }),
    db().usageLog.aggregate({ where: thisMonth, _count: { _all: true }, _avg: { latencyMs: true } }),
    db().usageLog.count({ where: { tenantId, timestamp: { gte: previousStart, lt: start } } }),
    db().usageLog.count({ where: { ...thisMonth, urgency: { gte: 4 } } }),
  ]);

  const daysInMonth = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 0)).getUTCDate();
  const counts = new Map(dailyRows.map((row) => [row.day, row.count]));
  const daily: DailyPoint[] = Array.from({ length: daysInMonth }, (_, index) => {
    const day = index + 1;
    const date = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), day));
    return { day, date: date.toISOString().slice(0, 10), count: counts.get(day) ?? 0 };
  });

  const categoryCounts = new Map(byCategory.map((row) => [row.category, row._count._all]));
  const categories = (Object.keys(CATEGORY_LABELS) as TicketCategory[])
    .map((category) => ({ category, label: CATEGORY_LABELS[category], count: categoryCounts.get(category) ?? 0 }))
    .sort((a, b) => b.count - a.count);

  return {
    monthLabel: new Intl.DateTimeFormat("de-DE", { month: "long", year: "numeric", timeZone: "UTC" }).format(start),
    totalThisMonth: aggregate._count._all,
    totalPreviousMonth: previous,
    daily,
    categories,
    avgLatencyMs: aggregate._avg.latencyMs === null ? null : Math.round(aggregate._avg.latencyMs),
    urgentCount: urgent,
  };
}
