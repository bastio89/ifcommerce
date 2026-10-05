import { NextResponse } from "next/server";
import type { z } from "zod";

export function jsonError(status: number, code: string, message: string, headers?: HeadersInit) {
  return NextResponse.json({ error: { code, message } }, { status, headers });
}

/**
 * CSRF-Schutz für Cookie-authentifizierte Mutationen: der Origin-Header muss zur
 * eigenen Domain passen (zusätzlich zu SameSite=Lax-Cookies).
 */
export function isSameOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

export async function parseJson<T extends z.ZodType>(
  request: Request,
  schema: T,
): Promise<{ data: z.infer<T>; error?: never } | { data?: never; error: NextResponse }> {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return { error: jsonError(400, "invalid_json", "Request-Body ist kein gültiges JSON.") };
  }
  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    const issue = parsed.error.issues[0];
    return { error: jsonError(422, "invalid_request", issue?.message ?? "Ungültige Eingabe.") };
  }
  return { data: parsed.data };
}

export function clientIp(request: Request): string {
  return request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || request.headers.get("x-real-ip") || "unknown";
}
