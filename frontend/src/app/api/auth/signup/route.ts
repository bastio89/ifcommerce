import { z } from "zod";

import { Prisma } from "@/generated/prisma/client";
import { createSession } from "@/lib/auth";
import { hashPassword } from "@/lib/crypto";
import { db } from "@/lib/db";
import { clientIp, isSameOrigin, jsonError, parseJson } from "@/lib/http";
import { rateLimit } from "@/lib/rate-limit";

const schema = z.object({
  shopName: z.string().trim().min(2, "Bitte gib den Namen deines Shops an.").max(120),
  shopUrl: z
    .string()
    .trim()
    .max(300)
    .optional()
    .transform((value) => value || undefined),
  email: z.email("Bitte gib eine gültige E-Mail-Adresse an.").transform((value) => value.toLowerCase()),
  password: z.string().min(10, "Das Passwort muss mindestens 10 Zeichen lang sein.").max(200),
});

export async function POST(request: Request) {
  if (!isSameOrigin(request)) return jsonError(403, "forbidden", "Ungültiger Origin.");
  const limit = rateLimit(`signup:${clientIp(request)}`, 5, 60 * 60 * 1000);
  if (!limit.ok) {
    return jsonError(429, "rate_limited", "Zu viele Registrierungen. Bitte später erneut versuchen.", {
      "retry-after": String(limit.retryAfter),
    });
  }

  const parsed = await parseJson(request, schema);
  if (parsed.error) return parsed.error;
  const { shopName, shopUrl, email, password } = parsed.data;

  const existing = await db().user.findUnique({ where: { email }, select: { id: true } });
  if (existing) {
    return jsonError(409, "email_taken", "Für diese E-Mail-Adresse existiert bereits ein Konto.");
  }

  const passwordHash = await hashPassword(password);
  let userId: string;
  try {
    const user = await db().user.create({
      data: {
        email,
        passwordHash,
        role: "OWNER",
        tenant: { create: { name: shopName, shopUrl } },
      },
      select: { id: true },
    });
    userId = user.id;
  } catch (error) {
    if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === "P2002") {
      return jsonError(409, "email_taken", "Für diese E-Mail-Adresse existiert bereits ein Konto.");
    }
    throw error;
  }

  await createSession(userId, request.headers.get("user-agent"));
  return Response.json({ ok: true }, { status: 201 });
}
