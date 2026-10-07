"""FastAPI-Einstiegspunkt der DecideCommerce Decision API."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import stripe
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import Scope

from app.config import Settings, get_settings
from app.container import Container
from app.db import create_pool
from app.decision.anthropic_engine import AnthropicDecisionEngine
from app.decision.base import DecisionEngine
from app.decision.heuristic_engine import HeuristicDecisionEngine
from app.decision.pipeline import DecisionPipeline
from app.decision.systemone_engine import SystemOneDecisionEngine
from app.middleware.api_key_auth import ApiKeyAuthMiddleware
from app.middleware.request_body_limit import RequestBodyLimitMiddleware
from app.routers import analysis_jobs, analyze, demo, health, webhooks
from app.services.analysis_jobs import AnalysisJobService
from app.services.entitlements import EntitlementService
from app.services.rate_limit import DatabaseTokenBucketRateLimiter
from app.services.stripe_sync import SubscriptionSyncService
from app.services.tenants import ApiKeyStore
from app.services.usage import StripeUsageReporter, UsageMeter

logger = logging.getLogger("decidecommerce")

ContainerFactory = Callable[[Settings], Awaitable[Container]]

_ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    413: "payload_too_large",
    429: "rate_limited",
    503: "service_unavailable",
}


def build_primary_engine(settings: Settings) -> DecisionEngine | None:
    """Wählt die Decision-Engine; None bedeutet: nur die Heuristik."""
    if settings.decision_engine == "systemone":
        return SystemOneDecisionEngine(settings)
    if settings.anthropic_enabled:
        return AnthropicDecisionEngine(settings)
    if settings.decision_engine == "anthropic":
        logger.warning("DECISION_ENGINE=anthropic, aber ANTHROPIC_API_KEY fehlt – nutze Heuristik.")
    return None


async def build_container(settings: Settings) -> Container:
    pool = await create_pool(settings)
    primary = build_primary_engine(settings)

    stripe_client: stripe.StripeClient | None = None
    if settings.stripe_enabled and settings.stripe_secret_key is not None:
        stripe_client = stripe.StripeClient(
            settings.stripe_secret_key.get_secret_value(), http_client=stripe.HTTPXClient()
        )

    api_keys = ApiKeyStore(pool, ttl_seconds=settings.api_key_cache_ttl_seconds)

    async def fetch_subscription(subscription_id: str) -> dict[str, Any] | None:
        if stripe_client is None:
            return None
        subscription = await stripe_client.v1.subscriptions.retrieve_async(subscription_id)
        return subscription.to_dict()

    pipeline = DecisionPipeline(primary=primary, fallback=HeuristicDecisionEngine())
    entitlements = EntitlementService(pool, free_tier_monthly_limit=settings.free_tier_monthly_limit)
    usage = UsageMeter(pool)
    analysis_jobs = AnalysisJobService(pool, pipeline, entitlements, usage, settings)
    container = Container(
        settings=settings,
        pool=pool,
        pipeline=pipeline,
        api_keys=api_keys,
        entitlements=entitlements,
        usage=usage,
        analysis_jobs=analysis_jobs,
        rate_limiter=DatabaseTokenBucketRateLimiter(pool),
        subscriptions=SubscriptionSyncService(
            pool,
            fetch_subscription=fetch_subscription if stripe_client else None,
            on_tenant_changed=api_keys.invalidate_tenant,
        ),
        stripe_client=stripe_client,
    )
    if stripe_client is not None and settings.stripe_meter_event_name:
        container.usage_reporter = StripeUsageReporter(
            pool,
            stripe_client,
            event_name=settings.stripe_meter_event_name,
            interval_seconds=settings.stripe_usage_report_interval_seconds,
        )
    return container


def _configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def create_app(settings: Settings | None = None, container_factory: ContainerFactory = build_container) -> FastAPI:
    settings = settings or get_settings()
    _configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        internal_secret = settings.internal_api_secret.get_secret_value() if settings.internal_api_secret else ""
        if settings.environment == "production" and (
            len(internal_secret) < 32 or internal_secret.lower().startswith(("change-me", "bitte-", "your-"))
        ):
            raise RuntimeError(
                "INTERNAL_API_SECRET muss in Produktion ein eigenes Secret mit mindestens 32 Zeichen sein."
            )
        container = await container_factory(settings)
        app.state.container = container
        container.analysis_jobs.start()
        if container.usage_reporter is not None:
            container.usage_reporter.start()
        engine = container.pipeline.primary
        # Lokale Modelle vorladen, ohne den Start zu blockieren (erster Ollama-Aufruf ist langsam).
        warm_up = getattr(engine, "warm_up", None)
        warm_up_task = asyncio.create_task(warm_up()) if warm_up is not None else None
        logger.info("DecideCommerce API ready (engine=%s)", container.pipeline.engine_name)
        try:
            yield
        finally:
            if warm_up_task is not None:
                warm_up_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await warm_up_task
            await container.analysis_jobs.stop()
            if container.usage_reporter is not None:
                await container.usage_reporter.stop()
            close_engine = getattr(engine, "aclose", None)
            if close_engine is not None:
                await close_engine()
            await container.pool.close()

    app = FastAPI(
        title="DecideCommerce Decision API",
        version="1.0.0",
        summary="Semantische If-Statements für den E-Commerce-Support.",
        description=(
            "Klassifiziert Support-Tickets und E-Mails in Echtzeit in ein festes Entscheidungsschema "
            "(Kategorie, Dringlichkeit, Intent-Flags, Konfidenz). Eine lokale Schutzschicht maskiert erkannte "
            "personenbezogene Daten vor dem Modellaufruf; die Erkennung ist nicht vollständig."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
    )

    def get_container(scope: Scope) -> Container:
        return scope["app"].state.container

    # Reihenfolge: zuletzt hinzugefügt = äußerste Schicht. CORS muss außen liegen,
    # damit auch 401/402/429-Antworten im Browser-Widget lesbar sind.
    app.add_middleware(
        RequestBodyLimitMiddleware,
        analysis_max_bytes=settings.max_request_body_bytes,
    )
    app.add_middleware(ApiKeyAuthMiddleware, container_getter=get_container)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=["POST", "GET", "OPTIONS"],
        allow_headers=["x-api-key", "content-type", "idempotency-key"],
        max_age=86_400,
    )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _ERROR_CODES.get(exc.status_code, "error")
        return JSONResponse(
            {"error": {"code": code, "message": str(exc.detail)}},
            status_code=exc.status_code,
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
        message = f"{location}: {first.get('msg', 'Ungültige Eingabe')}" if location else "Ungültige Eingabe"
        return JSONResponse({"error": {"code": "invalid_request", "message": message}}, status_code=422)

    app.include_router(health.router)
    app.include_router(analyze.router)
    app.include_router(analysis_jobs.router)
    app.include_router(webhooks.router)
    app.include_router(demo.router)
    return app


app = create_app()
