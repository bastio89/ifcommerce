import type { Metadata } from "next";

import { AuthForm } from "@/components/auth/auth-form";

export const metadata: Metadata = { title: "Anmelden" };

export default function LoginPage() {
  return (
    <>
      <h1 className="text-xl font-semibold tracking-tight">Willkommen zurück</h1>
      <p className="mt-1 mb-6 text-sm text-muted">Melde dich im Händler-Dashboard an.</p>
      <AuthForm mode="login" />
    </>
  );
}
