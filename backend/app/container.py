"""Komposition aller langlebigen Abhängigkeiten (ein Container pro Prozess)."""

from __future__ import annotations

from dataclasses import dataclass

import asyncpg
import stripe

from app.config import Settings
from app.decision.pipeline import DecisionPipeline
from app.services.entitlements import EntitlementService
from app.services.rate_limit import TokenBucketRateLimiter
from app.services.stripe_sync import SubscriptionSyncService
from app.services.tenants import ApiKeyStore
from app.services.usage import StripeUsageReporter, UsageMeter


@dataclass(slots=True)
class Container:
    settings: Settings
    pool: asyncpg.Pool
    pipeline: DecisionPipeline
    api_keys: ApiKeyStore
    entitlements: EntitlementService
    usage: UsageMeter
    rate_limiter: TokenBucketRateLimiter
    subscriptions: SubscriptionSyncService
    stripe_client: stripe.StripeClient | None = None
    usage_reporter: StripeUsageReporter | None = None
