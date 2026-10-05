"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import type { ApiError } from "@/lib/types";

type Mode = "login" | "signup";

export function AuthForm({ mode, redirectTo = "/dashboard" }: { mode: Mode; redirectTo?: string }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    const payload = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const response = await fetch(`/api/auth/${mode}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as ApiError | null;
        setError(body?.error.message ?? "Etwas ist schiefgelaufen.");
        return;
      }
      router.replace(redirectTo);
      router.refresh();
    } catch {
      setError("Netzwerkfehler – bitte erneut versuchen.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      {mode === "signup" && (
        <>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="shopName">Shop-Name</Label>
            <Input id="shopName" name="shopName" required autoComplete="organization" placeholder="Mein Shop GmbH" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="shopUrl">
              Shop-URL <span className="font-normal text-muted">(optional)</span>
            </Label>
            <Input id="shopUrl" name="shopUrl" type="url" placeholder="https://mein-shop.de" autoComplete="url" />
          </div>
        </>
      )}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="email">E-Mail</Label>
        <Input id="email" name="email" type="email" required autoComplete="email" placeholder="du@mein-shop.de" />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="password">Passwort</Label>
        <Input
          id="password"
          name="password"
          type="password"
          required
          minLength={mode === "signup" ? 10 : undefined}
          autoComplete={mode === "signup" ? "new-password" : "current-password"}
          placeholder={mode === "signup" ? "Mindestens 10 Zeichen" : "••••••••••"}
        />
      </div>

      {error && (
        <p role="alert" className="rounded-lg border border-critical/40 bg-critical/10 px-3 py-2 text-sm text-critical">
          {error}
        </p>
      )}

      <Button type="submit" disabled={pending} className="mt-2 w-full">
        {pending && <Loader2 className="size-4 animate-spin" aria-hidden />}
        {mode === "signup" ? "Konto erstellen" : "Anmelden"}
      </Button>

      <p className="text-center text-sm text-muted">
        {mode === "signup" ? (
          <>
            Schon registriert?{" "}
            <Link href="/login" className="text-foreground underline-offset-4 hover:underline">
              Anmelden
            </Link>
          </>
        ) : (
          <>
            Noch kein Konto?{" "}
            <Link href="/signup" className="text-foreground underline-offset-4 hover:underline">
              Kostenlos registrieren
            </Link>
          </>
        )}
      </p>
    </form>
  );
}
