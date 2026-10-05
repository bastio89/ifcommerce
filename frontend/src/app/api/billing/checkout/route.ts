import { getCurrentUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { env, stripeConfigured } from "@/lib/env";
import { isSameOrigin, jsonError } from "@/lib/http";
import { stripe } from "@/lib/stripe";

/** Startet Stripe Checkout für den Pro-Tarif (Grundgebühr + nutzungsbasierter Preis). */
export async function POST(request: Request) {
  if (!isSameOrigin(request)) return jsonError(403, "forbidden", "Ungültiger Origin.");
  const user = await getCurrentUser();
  if (!user) return jsonError(401, "unauthorized", "Bitte melde dich an.");
  if (!stripeConfigured()) return jsonError(503, "billing_unavailable", "Billing ist noch nicht konfiguriert.");

  const tenant = user.tenant;
  if (tenant.plan === "PRO" && ["ACTIVE", "TRIALING", "PAST_DUE"].includes(tenant.subscriptionStatus)) {
    return jsonError(409, "already_subscribed", "Dein Shop ist bereits auf Pro.");
  }

  const { APP_URL, STRIPE_PRICE_PRO_BASE, STRIPE_PRICE_PRO_METERED } = env();

  let customerId = tenant.stripeCustomerId;
  if (!customerId) {
    // Idempotency-Key verhindert doppelte Kunden bei parallelen Klicks.
    const customer = await stripe().customers.create(
      { email: user.email, name: tenant.name, metadata: { tenant_id: tenant.id } },
      { idempotencyKey: `customer-${tenant.id}` },
    );
    customerId = customer.id;
    await db().tenant.update({ where: { id: tenant.id }, data: { stripeCustomerId: customerId } });
  }

  const session = await stripe().checkout.sessions.create({
    mode: "subscription",
    customer: customerId,
    client_reference_id: tenant.id,
    line_items: [{ price: STRIPE_PRICE_PRO_BASE, quantity: 1 }, { price: STRIPE_PRICE_PRO_METERED }],
    subscription_data: { metadata: { tenant_id: tenant.id } },
    allow_promotion_codes: true,
    billing_address_collection: "required",
    tax_id_collection: { enabled: true },
    customer_update: { address: "auto", name: "auto" },
    success_url: `${APP_URL}/dashboard/billing?checkout=success`,
    cancel_url: `${APP_URL}/dashboard/billing?checkout=cancelled`,
  });

  if (!session.url) return jsonError(502, "stripe_error", "Stripe hat keine Checkout-URL geliefert.");
  return Response.json({ url: session.url });
}
