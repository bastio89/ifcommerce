from __future__ import annotations

import logging

import stripe
from fastapi import APIRouter, HTTPException, Request

from app.container import Container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["Webhooks"])


@router.post("/stripe", summary="Stripe-Webhook (Subscription-Lifecycle)")
async def stripe_webhook(request: Request) -> dict[str, str]:
    container: Container = request.app.state.container
    secret = container.settings.stripe_webhook_secret
    if secret is None or not secret.get_secret_value():
        raise HTTPException(status_code=503, detail="Stripe-Webhooks sind nicht konfiguriert.")

    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    try:
        # Signaturprüfung inkl. Replay-Schutz (Toleranz 5 Minuten).
        event = stripe.Webhook.construct_event(payload, signature, secret.get_secret_value())
    except (ValueError, stripe.SignatureVerificationError) as exc:
        logger.warning("Rejected Stripe webhook: %s", exc)
        raise HTTPException(status_code=400, detail="Ungültige Stripe-Signatur.") from exc

    outcome = await container.subscriptions.handle_event(event.to_dict())
    logger.info("Stripe event %s (%s): %s", event.id, event.type, outcome)
    return {"status": outcome}
