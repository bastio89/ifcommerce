import { z } from "zod";

import { env } from "@/lib/env";
import { clientIp, jsonError, parseJson } from "@/lib/http";
import { rateLimit } from "@/lib/rate-limit";

const schema = z.object({
  text: z.string().trim().min(3, "Bitte gib eine Testnachricht ein.").max(2000, "Maximal 2.000 Zeichen in der Demo."),
});

/**
 * Proxy für die Live-Demo der Landingpage. Der Browser spricht nie direkt mit der
 * Decision API; das interne Secret bleibt auf dem Server, Besucher werden pro IP limitiert.
 */
export async function POST(request: Request) {
  const ip = clientIp(request);
  for (const [window, limit, windowMs] of [
    ["minute", 8, 60_000],
    ["day", 60, 24 * 60 * 60_000],
  ] as const) {
    const result = rateLimit(`demo:${window}:${ip}`, limit, windowMs);
    if (!result.ok) {
      return jsonError(429, "rate_limited", "Demo-Limit erreicht. Registriere dich kostenlos für mehr Analysen.", {
        "retry-after": String(result.retryAfter),
      });
    }
  }

  const parsed = await parseJson(request, schema);
  if (parsed.error) return parsed.error;

  const { BACKEND_INTERNAL_URL, INTERNAL_API_SECRET } = env();
  if (!INTERNAL_API_SECRET) return jsonError(503, "demo_unavailable", "Die Live-Demo ist nicht konfiguriert.");

  try {
    const upstream = await fetch(`${BACKEND_INTERNAL_URL}/api/v1/demo/analyze-ticket`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-internal-secret": INTERNAL_API_SECRET },
      body: JSON.stringify({ text: parsed.data.text }),
      signal: AbortSignal.timeout(15_000),
      cache: "no-store",
    });
    const body = await upstream.json();
    return Response.json(body, { status: upstream.status });
  } catch {
    return jsonError(502, "backend_unreachable", "Die Decision API ist gerade nicht erreichbar.");
  }
}
