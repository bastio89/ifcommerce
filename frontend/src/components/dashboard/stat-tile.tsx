import { cn } from "@/lib/utils";

export function StatTile({
  label,
  value,
  detail,
  children,
  className,
}: {
  label: string;
  value: string;
  detail?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col rounded-xl border border-border bg-surface p-5", className)}>
      <div className="text-[13px] text-muted">{label}</div>
      <div className="mt-2 text-2xl font-semibold tracking-tight">{value}</div>
      {detail && <div className="mt-1 text-xs text-muted">{detail}</div>}
      {children}
    </div>
  );
}

/** Kontingent-Meter: Füllung trägt den Schweregrad, die Spur ist ein hellerer Ton derselben Rampe. */
export function QuotaMeter({ used, limit }: { used: number; limit: number }) {
  const share = limit > 0 ? Math.min(used / limit, 1) : 0;
  const fill = share >= 0.95 ? "bg-critical" : share >= 0.8 ? "bg-warning" : "bg-accent";
  const track = share >= 0.95 ? "bg-critical/20" : share >= 0.8 ? "bg-warning/20" : "bg-accent/20";
  return (
    <div
      className={cn("mt-3 h-1.5 overflow-hidden rounded-full", track)}
      role="meter"
      aria-valuemin={0}
      aria-valuemax={limit}
      aria-valuenow={used}
      aria-label="Verbrauchtes Monatskontingent"
    >
      <div className={cn("h-full rounded-full", fill)} style={{ width: `${share * 100}%` }} />
    </div>
  );
}
