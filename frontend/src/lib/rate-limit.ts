/**
 * Einfacher Fixed-Window-Limiter im Speicher (pro Next.js-Instanz).
 * Für mehrere Instanzen durch Redis/Upstash mit gleichem Interface ersetzen.
 */
const windows = new Map<string, { count: number; resetAt: number }>();

export function rateLimit(key: string, limit: number, windowMs: number): { ok: boolean; retryAfter: number } {
  const now = Date.now();
  const entry = windows.get(key);
  if (!entry || entry.resetAt <= now) {
    windows.set(key, { count: 1, resetAt: now + windowMs });
    if (windows.size > 50_000) {
      for (const [k, v] of windows) if (v.resetAt <= now) windows.delete(k);
    }
    return { ok: true, retryAfter: 0 };
  }
  entry.count += 1;
  if (entry.count > limit) {
    return { ok: false, retryAfter: Math.ceil((entry.resetAt - now) / 1000) };
  }
  return { ok: true, retryAfter: 0 };
}
