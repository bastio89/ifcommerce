import { randomBase62, sha256Hex } from "@/lib/crypto";

export const MAX_ACTIVE_KEYS = 10;

export type ApiKeyKind = "SECRET" | "PUBLISHABLE";

/**
 * Format identisch zum Backend (app/security.py):
 *   dc_sk_<40 Base62>  Secret Key       – Server-zu-Server
 *   dc_pk_<40 Base62>  Publishable Key  – Browser-Widget, an Origins gebunden
 */
export function generateApiKey(kind: ApiKeyKind) {
  const raw = `dc_${kind === "SECRET" ? "sk" : "pk"}_${randomBase62(40)}`;
  return {
    raw,
    hash: sha256Hex(raw),
    prefix: raw.slice(0, 10),
    last4: raw.slice(-4),
  };
}

/** Normalisiert eine Shop-Adresse auf ihren Origin, z. B. "https://mein-shop.de". */
export function normalizeOrigin(input: string): string | null {
  const value = input.trim();
  if (!value) return null;
  try {
    const url = new URL(value.includes("://") ? value : `https://${value}`);
    if (url.protocol !== "https:" && url.hostname !== "localhost") return null;
    return url.origin;
  } catch {
    return null;
  }
}
