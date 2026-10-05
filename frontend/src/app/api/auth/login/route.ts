import { z } from "zod";

import { createSession } from "@/lib/auth";
import { verifyPassword } from "@/lib/crypto";
import { db } from "@/lib/db";
import { clientIp, isSameOrigin, jsonError, parseJson } from "@/lib/http";
import { rateLimit } from "@/lib/rate-limit";

const schema = z.object({
  email: z.email("Bitte gib eine gültige E-Mail-Adresse an.").transform((value) => value.toLowerCase()),
  password: z.string().min(1, "Bitte gib dein Passwort ein.").max(200),
});

// Gegen Timing-Angriffe: auch bei unbekannter E-Mail einen Hash prüfen.
const DUMMY_HASH = ["scrypt", 2 ** 17, 8, 1, Buffer.alloc(16).toString("base64"), Buffer.alloc(64).toString("base64")].join(
  "$",
);

export async function POST(request: Request) {
  if (!isSameOrigin(request)) return jsonError(403, "forbidden", "Ungültiger Origin.");

  const parsed = await parseJson(request, schema);
  if (parsed.error) return parsed.error;
  const { email, password } = parsed.data;

  const limit = rateLimit(`login:${clientIp(request)}:${email}`, 10, 15 * 60 * 1000);
  if (!limit.ok) {
    return jsonError(429, "rate_limited", "Zu viele Anmeldeversuche. Bitte später erneut versuchen.", {
      "retry-after": String(limit.retryAfter),
    });
  }

  const user = await db().user.findUnique({ where: { email }, select: { id: true, passwordHash: true } });
  const valid = await verifyPassword(password, user?.passwordHash ?? DUMMY_HASH);
  if (!user || !valid) {
    return jsonError(401, "invalid_credentials", "E-Mail oder Passwort ist falsch.");
  }

  await createSession(user.id, request.headers.get("user-agent"));
  return Response.json({ ok: true });
}
