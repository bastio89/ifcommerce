import Stripe from "stripe";

import { env } from "@/lib/env";

let client: Stripe | undefined;

export function stripe(): Stripe {
  const key = env().STRIPE_SECRET_KEY;
  if (!key) throw new Error("STRIPE_SECRET_KEY ist nicht gesetzt.");
  client ??= new Stripe(key, { appInfo: { name: "DecideCommerce", version: "1.0.0" } });
  return client;
}
