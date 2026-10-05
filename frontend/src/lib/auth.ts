import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

import { randomBase62, sha256Hex } from "@/lib/crypto";
import { db } from "@/lib/db";
import { env } from "@/lib/env";

export const SESSION_COOKIE = "dc_session";
const SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000;

function cookieOptions(expires: Date) {
  return {
    httpOnly: true,
    // Auf HTTPS-Deployments immer "Secure"; lokal (http://localhost) nicht möglich.
    secure: env().APP_URL.startsWith("https://"),
    sameSite: "lax" as const,
    path: "/",
    expires,
  };
}

export async function createSession(userId: string, userAgent: string | null): Promise<void> {
  const token = randomBase62(48);
  const expiresAt = new Date(Date.now() + SESSION_TTL_MS);
  await db().session.create({
    data: { userId, tokenHash: sha256Hex(token), expiresAt, userAgent: userAgent?.slice(0, 255) ?? null },
  });
  (await cookies()).set(SESSION_COOKIE, token, cookieOptions(expiresAt));
}

export async function destroySession(): Promise<void> {
  const jar = await cookies();
  const token = jar.get(SESSION_COOKIE)?.value;
  if (token) {
    await db().session.deleteMany({ where: { tokenHash: sha256Hex(token) } });
  }
  jar.delete(SESSION_COOKIE);
}

/** Aktueller Nutzer inkl. Mandant – pro Request dedupliziert. */
export const getCurrentUser = cache(async () => {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return null;

  const session = await db().session.findUnique({
    where: { tokenHash: sha256Hex(token) },
    include: { user: { include: { tenant: true } } },
  });
  if (!session || session.expiresAt < new Date()) return null;
  return session.user;
});

export type CurrentUser = NonNullable<Awaited<ReturnType<typeof getCurrentUser>>>;

export async function requireUser(): Promise<CurrentUser> {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  return user;
}
