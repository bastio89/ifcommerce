import type { UsageOverview } from "@/lib/usage";

/** Ein Wert pro Kategorie -> eine Farbe für alle Balken; Identität trägt die Beschriftung. */
export function CategoryBreakdown({ categories }: { categories: UsageOverview["categories"] }) {
  const total = categories.reduce((sum, item) => sum + item.count, 0);
  const max = Math.max(1, ...categories.map((item) => item.count));

  return (
    <ul className="flex flex-col gap-4">
      {categories.map((item) => {
        const share = total > 0 ? Math.round((item.count / total) * 100) : 0;
        return (
          <li key={item.category}>
            <div className="mb-1.5 flex items-baseline justify-between gap-3 text-[13px]">
              <span className="truncate text-secondary">{item.label}</span>
              <span className="shrink-0 tabular-nums text-foreground">
                {item.count.toLocaleString("de-DE")} <span className="text-muted">· {share} %</span>
              </span>
            </div>
            <div className="h-2 rounded-full bg-white/[0.06]">
              <div
                className="h-full rounded-full bg-accent"
                style={{ width: `${(item.count / max) * 100}%`, minWidth: item.count > 0 ? 4 : 0 }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
