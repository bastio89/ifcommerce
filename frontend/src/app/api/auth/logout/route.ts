import { destroySession } from "@/lib/auth";
import { isSameOrigin, jsonError } from "@/lib/http";

export async function POST(request: Request) {
  if (!isSameOrigin(request)) return jsonError(403, "forbidden", "Ungültiger Origin.");
  await destroySession();
  return Response.json({ ok: true });
}
