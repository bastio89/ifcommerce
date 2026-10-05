import { getCurrentUser } from "@/lib/auth";
import { env, stripeConfigured } from "@/lib/env";
import { isSameOrigin, jsonError } from "@/lib/http";
import { stripe } from "@/lib/stripe";

/** Stripe Customer Portal: Zahlungsmethode, Rechnungen, Kündigung. */
export async function POST(request: Request) {
  if (!isSameOrigin(request)) return jsonError(403, "forbidden", "Ungültiger Origin.");
  const user = await getCurrentUser();
  if (!user) return jsonError(401, "unauthorized", "Bitte melde dich an.");
  if (!stripeConfigured()) return jsonError(503, "billing_unavailable", "Billing ist noch nicht konfiguriert.");
  if (!user.tenant.stripeCustomerId) {
    return jsonError(409, "no_customer", "Für deinen Shop existiert noch kein Stripe-Kundenkonto.");
  }

  const session = await stripe().billingPortal.sessions.create({
    customer: user.tenant.stripeCustomerId,
    return_url: `${env().APP_URL}/dashboard/billing`,
  });
  return Response.json({ url: session.url });
}
