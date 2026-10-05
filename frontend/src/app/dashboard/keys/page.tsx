import type { Metadata } from "next";

import { ApiKeyManager } from "@/components/dashboard/api-key-manager";
import { PageHeader } from "@/components/dashboard/page-header";
import { normalizeOrigin } from "@/lib/api-keys";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";

export const metadata: Metadata = { title: "API-Keys" };

export default async function KeysPage() {
  const user = await requireUser();
  const keys = await db().apiKey.findMany({
    where: { tenantId: user.tenantId },
    orderBy: { createdAt: "desc" },
    select: {
      id: true,
      name: true,
      type: true,
      prefix: true,
      last4: true,
      allowedOrigins: true,
      lastUsedAt: true,
      revokedAt: true,
      createdAt: true,
    },
  });

  return (
    <>
      <PageHeader
        title="API-Keys"
        description="Schlüssel für den Header x-api-key. Gespeichert wird nur ein SHA-256-Hash. Ein Widerruf greift innerhalb von Sekunden."
      />
      <ApiKeyManager
        defaultOrigin={user.tenant.shopUrl ? (normalizeOrigin(user.tenant.shopUrl) ?? "") : ""}
        initialKeys={keys.map((key) => ({
          ...key,
          lastUsedAt: key.lastUsedAt?.toISOString() ?? null,
          revokedAt: key.revokedAt?.toISOString() ?? null,
          createdAt: key.createdAt.toISOString(),
        }))}
      />
    </>
  );
}
