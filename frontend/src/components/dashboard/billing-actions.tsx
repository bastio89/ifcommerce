"use client";

import { ExternalLink, Loader2, Sparkles } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import type { ApiError } from "@/lib/types";

export function BillingAction({ action, label }: { action: "checkout" | "portal"; label: string }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function go() {
    setPending(true);
    setError(null);
    try {
      const response = await fetch(`/api/billing/${action}`, { method: "POST" });
      const body = (await response.json()) as { url: string } | ApiError;
      if (!response.ok || "error" in body) {
        setError("error" in body ? body.error.message : "Stripe ist gerade nicht erreichbar.");
        setPending(false);
        return;
      }
      window.location.assign(body.url);
    } catch {
      setError("Netzwerkfehler – bitte erneut versuchen.");
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col items-start gap-2">
      <Button variant={action === "checkout" ? "accent" : "secondary"} onClick={go} disabled={pending}>
        {pending ? (
          <Loader2 className="size-4 animate-spin" aria-hidden />
        ) : action === "checkout" ? (
          <Sparkles className="size-4" aria-hidden />
        ) : (
          <ExternalLink className="size-4" aria-hidden />
        )}
        {label}
      </Button>
      {error && (
        <p role="alert" className="text-sm text-critical">
          {error}
        </p>
      )}
    </div>
  );
}
