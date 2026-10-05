import type { Metadata } from "next";

import { IntegrationGuide } from "@/components/dashboard/integration-guide";
import { PageHeader } from "@/components/dashboard/page-header";
import { requireUser } from "@/lib/auth";
import { env } from "@/lib/env";

export const metadata: Metadata = { title: "Integration" };

export default async function IntegrationPage() {
  await requireUser();
  const { APP_URL, PUBLIC_API_BASE_URL } = env();
  return (
    <>
      <PageHeader
        title="Integration"
        description="Binde DecideCommerce per Script-Tag in dein Kontaktformular ein oder rufe die REST-API aus deinem Helpdesk auf."
      />
      <IntegrationGuide appUrl={APP_URL} apiUrl={PUBLIC_API_BASE_URL} />
    </>
  );
}
