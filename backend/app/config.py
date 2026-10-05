"""Zentrale, typisierte Konfiguration (12-Factor: alles kommt aus ENV-Variablen)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Query-Parameter, die nur Prisma versteht. asyncpg würde sie als
# Postgres-Laufzeitparameter senden und mit einem Fehler abbrechen.
_PRISMA_ONLY_DSN_PARAMS = {
    "schema",
    "connection_limit",
    "pool_timeout",
    "pgbouncer",
    "socket_timeout",
    "statement_cache_size",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # --- Datenbank (Schema & Migrationen werden von Prisma verwaltet) ---
    database_url: str = "postgresql://decide:decide@localhost:5432/decidecommerce"
    db_pool_min_size: int = 2
    db_pool_max_size: int = 20

    # --- KI-Decision-Engine ---
    # auto      -> Anthropic, falls ein API-Key gesetzt ist, sonst Heuristik
    # anthropic -> immer das LLM (Heuristik nur als Fallback bei Fehlern)
    # heuristic -> deterministische, lokale Regel-Engine (kein externer Call)
    decision_engine: Literal["auto", "anthropic", "heuristic"] = "auto"
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-opus-5-5"
    # Klassifikation braucht kaum Denkaufwand: "low" minimiert Latenz & Kosten.
    anthropic_effort: Literal["low", "medium", "high", "xhigh", "max", ""] = "low"
    anthropic_timeout_seconds: float = 10.0
    anthropic_max_retries: int = 1
    # Serverseitiger Refusal-Fallback (nur für Modelle, die ihn unterstützen).
    anthropic_server_fallbacks: bool = True

    max_ticket_chars: int = 20_000

    # --- Billing / Stripe ---
    stripe_secret_key: SecretStr | None = None
    stripe_webhook_secret: SecretStr | None = None
    # Event-Name des Stripe Billing Meters für Usage-Based Billing (Pro-Tarif).
    stripe_meter_event_name: str = "decidecommerce_ticket_analyzed"
    stripe_usage_report_interval_seconds: float = 30.0
    free_tier_monthly_limit: int = 250

    # --- Sicherheit / Plattform ---
    # Geteiltes Secret zwischen Next.js-Server und Backend (Live-Demo-Proxy).
    internal_api_secret: SecretStr | None = None
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["*"])
    api_key_cache_ttl_seconds: float = 15.0
    rate_limit_secret_key_per_minute: int = 600
    rate_limit_publishable_key_per_minute: int = 60

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def asyncpg_dsn(self) -> str:
        """DATABASE_URL ohne Prisma-spezifische Parameter (asyncpg-kompatibel)."""
        parts = urlsplit(self.database_url)
        query = [(k, v) for k, v in parse_qsl(parts.query) if k not in _PRISMA_ONLY_DSN_PARAMS]
        scheme = "postgresql" if parts.scheme in {"postgres", "postgresql"} else parts.scheme
        return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    @property
    def llm_enabled(self) -> bool:
        if self.decision_engine == "heuristic":
            return False
        return bool(self.anthropic_api_key and self.anthropic_api_key.get_secret_value())

    @property
    def stripe_enabled(self) -> bool:
        return bool(self.stripe_secret_key and self.stripe_secret_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
