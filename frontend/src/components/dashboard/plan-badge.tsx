import { Badge } from "@/components/ui/badge";
import type { Plan, SubscriptionStatus } from "@/generated/prisma/enums";

export function PlanBadge({ plan, status }: { plan: Plan; status: SubscriptionStatus }) {
  if (plan === "PRO") {
    if (status === "PAST_DUE") return <Badge tone="warning">Pro · Zahlung offen</Badge>;
    if (status === "UNPAID" || status === "PAUSED") return <Badge tone="critical">Pro · gesperrt</Badge>;
    if (status === "INCOMPLETE") return <Badge tone="warning">Pro · Zahlung ausstehend</Badge>;
    if (status === "TRIALING") return <Badge tone="accent">Pro · Testphase</Badge>;
    return <Badge tone="accent">Pro</Badge>;
  }
  return <Badge>Free</Badge>;
}
