import { z } from "zod";

/**
 * Serverseitige Konfiguration. Bewusst ohne NEXT_PUBLIC_-Variablen: Werte werden
 * zur Laufzeit gelesen, damit ein einziges Docker-Image in jeder Umgebung läuft.
 */
const schema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  DATABASE_URL: z.string().min(1).optional(),
  /** Öffentliche Basis-URL dieser App (Redirects, Stripe-Rücksprung, Cookies). */
  APP_URL: z.url().default("http://localhost:3000"),
  /** Öffentliche URL der Decision API (für Snippets und das Widget). */
  PUBLIC_API_BASE_URL: z.url().default("http://localhost:8000"),
  /** Interne URL der Decision API (Docker-Netzwerk) für Server-zu-Server-Aufrufe. */
  BACKEND_INTERNAL_URL: z.url().default("http://localhost:8000"),
  INTERNAL_API_SECRET: z.string().optional(),
  STRIPE_SECRET_KEY: z.string().optional(),
  STRIPE_PRICE_PRO_BASE: z.string().optional(),
  STRIPE_PRICE_PRO_METERED: z.string().optional(),
  FREE_TIER_MONTHLY_LIMIT: z.coerce.number().int().positive().default(250),
});

export type Env = z.infer<typeof schema>;

let cached: Env | undefined;

export function env(): Env {
  if (!cached) {
    const parsed = schema.safeParse(process.env);
    if (!parsed.success) {
      throw new Error(`Ungültige Konfiguration: ${z.prettifyError(parsed.error)}`);
    }
    cached = parsed.data;
  }
  return cached;
}

export function stripeConfigured(): boolean {
  const e = env();
  return Boolean(e.STRIPE_SECRET_KEY && e.STRIPE_PRICE_PRO_BASE && e.STRIPE_PRICE_PRO_METERED);
}
