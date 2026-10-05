import { z } from "zod";

import { MAX_ACTIVE_KEYS, generateApiKey, normalizeOrigin } from "@/lib/api-keys";
import { getCurrentUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { isSameOrigin, jsonError, parseJson } from "@/lib/http";

export const dynamic = "force-dynamic";

const keySelect = {
  id: true,
  name: true,
  type: true,
  prefix: true,
  last4: true,
  allowedOrigins: true,
  lastUsedAt: true,
  revokedAt: true,
  createdAt: true,
} as const;

const createSchema = z
  .object({
    name: z.string().trim().min(1, "Bitte gib dem Schlüssel einen Namen.").max(80),
    type: z.enum(["SECRET", "PUBLISHABLE"]).default("SECRET"),
    allowedOrigins: z.array(z.string().max(300)).max(20).default([]),
  })
  .transform((value, ctx) => {
    const origins = value.allowedOrigins.map(normalizeOrigin);
    if (origins.some((origin) => origin === null)) {
      ctx.addIssue({ code: "custom", message: "Ungültige Domain. Beispiel: https://mein-shop.de" });
      return z.NEVER;
    }
    if (value.type === "PUBLISHABLE" && origins.length === 0) {
      ctx.addIssue({ code: "custom", message: "Publishable Keys benötigen mindestens eine freigegebene Domain." });
      return z.NEVER;
    }
    return { ...value, allowedOrigins: [...new Set(origins as string[])] };
  });

export async function GET() {
  const user = await getCurrentUser();
  if (!user) return jsonError(401, "unauthorized", "Bitte melde dich an.");

  const keys = await db().apiKey.findMany({
    where: { tenantId: user.tenantId },
    orderBy: [{ revokedAt: { sort: "asc", nulls: "first" } }, { createdAt: "desc" }],
    select: keySelect,
  });
  return Response.json({ keys });
}

export async function POST(request: Request) {
  if (!isSameOrigin(request)) return jsonError(403, "forbidden", "Ungültiger Origin.");
  const user = await getCurrentUser();
  if (!user) return jsonError(401, "unauthorized", "Bitte melde dich an.");

  const parsed = await parseJson(request, createSchema);
  if (parsed.error) return parsed.error;

  const active = await db().apiKey.count({ where: { tenantId: user.tenantId, revokedAt: null } });
  if (active >= MAX_ACTIVE_KEYS) {
    return jsonError(409, "key_limit_reached", `Maximal ${MAX_ACTIVE_KEYS} aktive Schlüssel. Bitte widerrufe zuerst einen.`);
  }

  const generated = generateApiKey(parsed.data.type);
  const key = await db().apiKey.create({
    data: {
      tenantId: user.tenantId,
      name: parsed.data.name,
      type: parsed.data.type,
      keyHash: generated.hash,
      prefix: generated.prefix,
      last4: generated.last4,
      allowedOrigins: parsed.data.type === "PUBLISHABLE" ? parsed.data.allowedOrigins : [],
    },
    select: keySelect,
  });

  // Der Klartext-Schlüssel verlässt den Server genau einmal – gespeichert wird nur der Hash.
  return Response.json({ key, secret: generated.raw }, { status: 201 });
}
