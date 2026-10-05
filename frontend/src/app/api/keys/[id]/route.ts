import { z } from "zod";

import { getCurrentUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { isSameOrigin, jsonError } from "@/lib/http";

/** Widerruft einen Schlüssel. Er wird nicht gelöscht, damit die Nutzungshistorie erhalten bleibt. */
export async function DELETE(request: Request, context: RouteContext<"/api/keys/[id]">) {
  if (!isSameOrigin(request)) return jsonError(403, "forbidden", "Ungültiger Origin.");
  const user = await getCurrentUser();
  if (!user) return jsonError(401, "unauthorized", "Bitte melde dich an.");

  const { id } = await context.params;
  if (!z.uuid().safeParse(id).success) return jsonError(404, "not_found", "Schlüssel nicht gefunden.");
  const result = await db().apiKey.updateMany({
    where: { id, tenantId: user.tenantId, revokedAt: null },
    data: { revokedAt: new Date() },
  });
  if (result.count === 0) return jsonError(404, "not_found", "Schlüssel nicht gefunden oder bereits widerrufen.");
  return Response.json({ ok: true });
}
