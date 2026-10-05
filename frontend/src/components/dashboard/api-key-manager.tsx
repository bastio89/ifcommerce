"use client";

import { AlertTriangle, Globe, KeyRound, Loader2, Plus, ShieldAlert, Trash2, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CopyButton } from "@/components/ui/copy-button";
import { Input, Label, Textarea } from "@/components/ui/input";
import type { ApiError } from "@/lib/types";
import { cn } from "@/lib/utils";

export type ApiKeyRow = {
  id: string;
  name: string;
  type: "SECRET" | "PUBLISHABLE";
  prefix: string;
  last4: string;
  allowedOrigins: string[];
  lastUsedAt: string | null;
  revokedAt: string | null;
  createdAt: string;
};

const dateFormat = new Intl.DateTimeFormat("de-DE", { dateStyle: "medium", timeStyle: "short" });

function formatDate(value: string | null): string {
  return value ? dateFormat.format(new Date(value)) : "–";
}

function maskedKey(key: ApiKeyRow): string {
  return `${key.prefix}${"•".repeat(12)}${key.last4}`;
}

export function ApiKeyManager({ initialKeys, defaultOrigin }: { initialKeys: ApiKeyRow[]; defaultOrigin: string }) {
  const router = useRouter();
  const [keys, setKeys] = useState(initialKeys);
  const [showForm, setShowForm] = useState(initialKeys.length === 0);
  const [type, setType] = useState<ApiKeyRow["type"]>("SECRET");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<{ name: string; secret: string; type: ApiKeyRow["type"] } | null>(null);
  const [confirmRevoke, setConfirmRevoke] = useState<string | null>(null);

  async function createKey(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const origins = String(form.get("origins") ?? "")
      .split(/[\s,]+/)
      .filter(Boolean);
    setPending(true);
    setError(null);
    try {
      const response = await fetch("/api/keys", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: form.get("name"), type, allowedOrigins: type === "PUBLISHABLE" ? origins : [] }),
      });
      const body = (await response.json()) as { key: ApiKeyRow; secret: string } | ApiError;
      if (!response.ok || "error" in body) {
        setError("error" in body ? body.error.message : "Schlüssel konnte nicht erstellt werden.");
        return;
      }
      setKeys((current) => [body.key, ...current]);
      setRevealed({ name: body.key.name, secret: body.secret, type: body.key.type });
      setShowForm(false);
      router.refresh();
    } catch {
      setError("Netzwerkfehler – bitte erneut versuchen.");
    } finally {
      setPending(false);
    }
  }

  async function revoke(id: string) {
    setPending(true);
    setError(null);
    try {
      const response = await fetch(`/api/keys/${id}`, { method: "DELETE" });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as ApiError | null;
        setError(body?.error.message ?? "Widerruf fehlgeschlagen.");
        return;
      }
      setKeys((current) =>
        current.map((key) => (key.id === id ? { ...key, revokedAt: new Date().toISOString() } : key)),
      );
      router.refresh();
    } finally {
      setConfirmRevoke(null);
      setPending(false);
    }
  }

  const active = keys.filter((key) => !key.revokedAt);
  const revoked = keys.filter((key) => key.revokedAt);

  return (
    <div className="flex flex-col gap-6">
      {revealed && (
        <div className="rounded-xl border border-good/40 bg-good/[0.07] p-5" role="status">
          <div className="mb-1 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 font-medium">
              <ShieldAlert className="size-4 text-good" aria-hidden />
              „{revealed.name}“ wurde erstellt
            </div>
            <button
              type="button"
              onClick={() => setRevealed(null)}
              className="rounded-md p-1 text-muted hover:text-foreground"
              aria-label="Hinweis schließen"
            >
              <X className="size-4" aria-hidden />
            </button>
          </div>
          <p className="mb-3 text-sm text-secondary">
            Kopiere den Schlüssel jetzt. Aus Sicherheitsgründen speichern wir nur einen Hash und können ihn nie wieder
            anzeigen.
            {revealed.type === "SECRET" && " Secret Keys gehören nie in Browser-Code."}
          </p>
          <div className="flex flex-col gap-2 rounded-lg border border-border-strong bg-background p-3 sm:flex-row sm:items-center">
            <code className="flex-1 font-mono text-[13px] break-all text-foreground">{revealed.secret}</code>
            <CopyButton value={revealed.secret} label="Schlüssel kopieren" />
          </div>
        </div>
      )}

      {error && (
        <div role="alert" className="rounded-lg border border-critical/40 bg-critical/10 px-3 py-2 text-sm text-critical">
          {error}
        </div>
      )}

      {showForm ? (
        <form onSubmit={createKey} className="rounded-xl border border-border bg-surface p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-semibold">Neuen Schlüssel erzeugen</h2>
            {keys.length > 0 && (
              <Button variant="ghost" size="sm" onClick={() => setShowForm(false)}>
                Abbrechen
              </Button>
            )}
          </div>

          <fieldset className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <legend className="sr-only">Schlüsseltyp</legend>
            {(
              [
                {
                  value: "SECRET",
                  title: "Secret Key",
                  icon: KeyRound,
                  text: "Für Server, Helpdesk-Automationen und Backend-Integrationen.",
                },
                {
                  value: "PUBLISHABLE",
                  title: "Publishable Key",
                  icon: Globe,
                  text: "Für das Browser-Widget. Funktioniert nur auf freigegebenen Domains.",
                },
              ] as const
            ).map(({ value, title, icon: Icon, text }) => (
              <label
                key={value}
                className={cn(
                  "flex cursor-pointer gap-3 rounded-lg border p-3 transition-colors",
                  type === value ? "border-accent/60 bg-accent/[0.07]" : "border-border-strong hover:bg-white/[0.03]",
                )}
              >
                <input
                  type="radio"
                  name="type"
                  value={value}
                  checked={type === value}
                  onChange={() => setType(value)}
                  className="sr-only"
                />
                <Icon className="mt-0.5 size-4 shrink-0 text-accent-strong" aria-hidden />
                <span>
                  <span className="block text-sm font-medium">{title}</span>
                  <span className="block text-xs text-muted">{text}</span>
                </span>
              </label>
            ))}
          </fieldset>

          <div className="grid grid-cols-1 gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="key-name">Name</Label>
              <Input
                id="key-name"
                name="name"
                required
                maxLength={80}
                placeholder={type === "SECRET" ? "z. B. Zendesk-Automation" : "z. B. Kontaktformular Shop"}
              />
            </div>
            {type === "PUBLISHABLE" && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="key-origins">Freigegebene Domains</Label>
                <Textarea
                  id="key-origins"
                  name="origins"
                  rows={2}
                  required
                  defaultValue={defaultOrigin}
                  placeholder="https://mein-shop.de, https://www.mein-shop.de"
                  className="font-mono text-[13px]"
                />
                <span className="text-xs text-muted">Komma- oder zeilengetrennt. Nur HTTPS (außer localhost).</span>
              </div>
            )}
          </div>

          <Button type="submit" variant="accent" disabled={pending} className="mt-5">
            {pending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Plus className="size-4" aria-hidden />}
            Schlüssel generieren
          </Button>
        </form>
      ) : (
        <div>
          <Button variant="accent" onClick={() => setShowForm(true)}>
            <Plus className="size-4" aria-hidden />
            Neuer API-Key
          </Button>
        </div>
      )}

      <section aria-labelledby="active-keys">
        <h2 id="active-keys" className="mb-3 text-sm font-medium text-secondary">
          Aktive Schlüssel ({active.length})
        </h2>
        {active.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border-strong p-8 text-center text-sm text-muted">
            Noch keine aktiven Schlüssel.
          </div>
        ) : (
          <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
            {active.map((key) => (
              <li key={key.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{key.name}</span>
                    <Badge tone={key.type === "SECRET" ? "neutral" : "accent"}>
                      {key.type === "SECRET" ? "Secret" : "Publishable"}
                    </Badge>
                  </div>
                  <code className="mt-1 block font-mono text-[12.5px] text-muted">{maskedKey(key)}</code>
                  <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                    <span>Erstellt {formatDate(key.createdAt)}</span>
                    <span>Zuletzt genutzt {formatDate(key.lastUsedAt)}</span>
                    {key.type === "PUBLISHABLE" && <span>Domains: {key.allowedOrigins.join(", ")}</span>}
                  </div>
                </div>
                {confirmRevoke === key.id ? (
                  <div className="flex shrink-0 items-center gap-2">
                    <span className="flex items-center gap-1 text-xs text-warning">
                      <AlertTriangle className="size-3.5" aria-hidden /> Sofort ungültig
                    </span>
                    <Button variant="danger" size="sm" disabled={pending} onClick={() => revoke(key.id)}>
                      Widerrufen
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setConfirmRevoke(null)}>
                      Abbrechen
                    </Button>
                  </div>
                ) : (
                  <Button variant="ghost" size="sm" onClick={() => setConfirmRevoke(key.id)} className="shrink-0">
                    <Trash2 className="size-4" aria-hidden />
                    Widerrufen
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {revoked.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-muted hover:text-foreground">
            Widerrufene Schlüssel ({revoked.length})
          </summary>
          <ul className="mt-3 divide-y divide-border rounded-xl border border-border">
            {revoked.map((key) => (
              <li key={key.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-muted">
                <span>
                  {key.name} · <code className="font-mono text-xs">{maskedKey(key)}</code>
                </span>
                <span className="text-xs">Widerrufen {formatDate(key.revokedAt)}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
