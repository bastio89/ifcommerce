import { redirect } from "next/navigation";

import { Logo } from "@/components/ui/logo";
import { getCurrentUser } from "@/lib/auth";

export default async function AuthLayout({ children }: { children: React.ReactNode }) {
  if (await getCurrentUser()) redirect("/dashboard");

  return (
    <div className="relative flex min-h-dvh flex-col items-center justify-center px-4 py-12">
      <div className="bg-grid pointer-events-none absolute inset-0" aria-hidden />
      <div className="glow pointer-events-none absolute inset-x-0 top-0 h-96" aria-hidden />
      <div className="relative w-full max-w-sm">
        <div className="mb-8 flex justify-center">
          <Logo />
        </div>
        <div className="rounded-2xl border border-border bg-surface p-6 shadow-2xl shadow-black/40 sm:p-8">{children}</div>
      </div>
    </div>
  );
}
