import type { Metadata } from "next";

import { LogoutButton } from "@/components/dashboard/logout-button";
import { PlanBadge } from "@/components/dashboard/plan-badge";
import { SidebarNav } from "@/components/dashboard/sidebar-nav";
import { Logo } from "@/components/ui/logo";
import { requireUser } from "@/lib/auth";

export const metadata: Metadata = { title: "Dashboard" };

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const user = await requireUser();

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[248px_minmax(0,1fr)]">
      <aside className="border-b border-border bg-surface/50 lg:sticky lg:top-0 lg:h-dvh lg:border-r lg:border-b-0">
        <div className="flex flex-col gap-4 p-4 lg:h-full lg:gap-6 lg:p-5">
          <div className="flex items-center justify-between">
            <Logo href="/dashboard" />
            <div className="lg:hidden">
              <LogoutButton />
            </div>
          </div>
          <div className="hidden rounded-lg border border-border bg-background/60 p-3 lg:block">
            <div className="truncate text-sm font-medium">{user.tenant.name}</div>
            <div className="mt-1 truncate text-xs text-muted">{user.email}</div>
            <div className="mt-2.5">
              <PlanBadge plan={user.tenant.plan} status={user.tenant.subscriptionStatus} />
            </div>
          </div>
          <SidebarNav />
          <div className="mt-auto hidden lg:block">
            <LogoutButton />
          </div>
        </div>
      </aside>
      <main className="min-w-0 px-4 py-8 sm:px-8 lg:py-10">
        <div className="mx-auto max-w-5xl">{children}</div>
      </main>
    </div>
  );
}
