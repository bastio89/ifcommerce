import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

export const fieldClasses =
  "w-full rounded-lg border border-border-strong bg-background px-3 text-sm text-foreground placeholder:text-muted/70 transition-colors focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/25 disabled:opacity-60";

export function Input({ className, ...props }: ComponentProps<"input">) {
  return <input className={cn(fieldClasses, "h-10", className)} {...props} />;
}

export function Textarea({ className, ...props }: ComponentProps<"textarea">) {
  return <textarea className={cn(fieldClasses, "py-2.5 leading-relaxed", className)} {...props} />;
}

export function Label({ className, ...props }: ComponentProps<"label">) {
  return <label className={cn("text-[13px] font-medium text-secondary", className)} {...props} />;
}
