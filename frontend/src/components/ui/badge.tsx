import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

type Tone = "neutral" | "accent" | "good" | "warning" | "serious" | "critical";

const tones: Record<Tone, string> = {
  neutral: "border-border-strong bg-white/5 text-secondary",
  accent: "border-accent/40 bg-accent/10 text-accent-strong",
  good: "border-good/40 bg-good/10 text-good",
  warning: "border-warning/40 bg-warning/10 text-warning",
  serious: "border-serious/40 bg-serious/10 text-serious",
  critical: "border-critical/40 bg-critical/10 text-critical",
};

export function Badge({ tone = "neutral", className, ...props }: ComponentProps<"span"> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
