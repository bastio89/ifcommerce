"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TooltipContentProps, TooltipValueType } from "recharts";

import type { DailyPoint } from "@/lib/usage";

const ACCENT = "#7c6cf0"; // validiert gegen die Kartenfläche (≥ 3:1)
const ACCENT_HOVER = "#9a8cff";
const GRID = "#24252a";
const AXIS_TEXT = "#8a8d97";

const dayFormat = new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "short", timeZone: "UTC" });

function ChartTooltip({ active, payload }: TooltipContentProps<TooltipValueType, string | number>) {
  const point = payload?.[0]?.payload as DailyPoint | undefined;
  if (!active || !point) return null;
  return (
    <div className="rounded-lg border border-border-strong bg-surface-2 px-3 py-2 shadow-xl shadow-black/40">
      <div className="text-sm font-semibold text-foreground">{point.count.toLocaleString("de-DE")} Analysen</div>
      <div className="text-xs text-muted">{dayFormat.format(new Date(point.date))}</div>
    </div>
  );
}

export function UsageChart({ data }: { data: DailyPoint[] }) {
  return (
    <div className="h-64 w-full" role="img" aria-label="Analysierte Tickets pro Tag im laufenden Monat">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: -12 }} barCategoryGap={2}>
          <CartesianGrid vertical={false} stroke={GRID} strokeWidth={1} />
          <XAxis
            dataKey="day"
            tickLine={false}
            axisLine={{ stroke: "#383835" }}
            tick={{ fill: AXIS_TEXT, fontSize: 11 }}
            interval={0}
            tickFormatter={(day: number) => (day === 1 || day % 5 === 0 ? String(day) : "")}
          />
          <YAxis
            allowDecimals={false}
            tickLine={false}
            axisLine={false}
            tick={{ fill: AXIS_TEXT, fontSize: 11, style: { fontVariantNumeric: "tabular-nums" } }}
            tickFormatter={(value: number) => value.toLocaleString("de-DE")}
            width={48}
          />
          <Tooltip content={ChartTooltip} cursor={{ fill: "rgb(255 255 255 / 0.04)" }} isAnimationActive={false} />
          <Bar
            dataKey="count"
            fill={ACCENT}
            radius={[4, 4, 0, 0]}
            maxBarSize={24}
            activeBar={{ fill: ACCENT_HOVER }}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
