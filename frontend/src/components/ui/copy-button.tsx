"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

export function CopyButton({ value, label = "Kopieren", className }: { value: string; label?: string; className?: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      aria-label={copied ? "Kopiert" : label}
      className={cn(
        "inline-flex h-7 items-center gap-1.5 rounded-md border border-border-strong bg-surface-2 px-2 text-xs text-secondary transition-colors hover:text-foreground",
        className,
      )}
    >
      {copied ? <Check className="size-3.5 text-good" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
      {copied ? "Kopiert" : label}
    </button>
  );
}
