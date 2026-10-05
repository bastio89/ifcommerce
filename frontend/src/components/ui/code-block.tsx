import { CopyButton } from "@/components/ui/copy-button";
import { cn } from "@/lib/utils";

export function CodeBlock({ code, title, className }: { code: string; title?: string; className?: string }) {
  return (
    <div className={cn("overflow-hidden rounded-xl border border-border bg-background", className)}>
      <div className="flex items-center justify-between border-b border-border bg-surface px-4 py-2">
        <span className="font-mono text-xs text-muted">{title ?? "code"}</span>
        <CopyButton value={code} />
      </div>
      <pre className="overflow-x-auto p-4 font-mono text-[12.5px] leading-relaxed text-secondary">
        <code>{code}</code>
      </pre>
    </div>
  );
}
