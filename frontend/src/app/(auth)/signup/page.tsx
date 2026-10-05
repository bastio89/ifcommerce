import type { Metadata } from "next";

import { AuthForm } from "@/components/auth/auth-form";

export const metadata: Metadata = { title: "Kostenlos starten" };

export default async function SignupPage({ searchParams }: PageProps<"/signup">) {
  const { plan } = await searchParams;
  return (
    <>
      <h1 className="text-xl font-semibold tracking-tight">Kostenlos starten</h1>
      <p className="mt-1 mb-6 text-sm text-muted">Keine Kreditkarte nötig. Upgrade auf Pro jederzeit im Dashboard.</p>
      <AuthForm mode="signup" redirectTo={plan === "pro" ? "/dashboard/billing" : "/dashboard/keys"} />
    </>
  );
}
