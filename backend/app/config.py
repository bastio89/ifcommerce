"""Zentrale, typisierte Konfiguration (12-Factor: alles kommt aus ENV-Variablen)."""

from __future__ import annotations

import ssl
from functools import lru_cache
from typing import Annotated, Any, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Query-Parameter, die nur Prisma bzw. libpq verstehen. asyncpg würde sie als
# Postgres-Laufzeitparameter senden und mit einem Fehler abbrechen (z. B. Neons
# Standard-URL mit channel_binding=require: "unsupported startup parameter").
_NON_ASYNCPG_DSN_PARAMS = {
    "schema",
    "connection_limit",
    "pool_timeout",
    "pgbouncer",
    "socket_timeout",
    "statement_cache_size",
    "channel_binding",
    "uselibpqcompat",
    "connect_timeout",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # --- Datenbank (Schema & Migrationen werden von Prisma verwaltet) ---
    database_url: str = "postgresql://decide:decide@localhost:5432/decidecommerce"
    db_pool_min_size: int = 2
    db_pool_max_size: int = 20
    # None = automatisch: 0 hinter PgBouncer/Neon-Pooler (Host enthält "-pooler"), sonst asyncpg-Default.
    db_statement_cache_size: int | None = None

    # --- KI-Decision-Engine ---
    # auto      -> Anthropic, falls ein API-Key gesetzt ist, sonst Heuristik
    # systemone -> Decision-Modell über /v1/systemone: lokal mit Ollama (Tev1) oder TypeSafe Jev
    # anthropic -> immer Claude (Heuristik nur als Fallback bei Fehlern)
    # heuristic -> deterministische, lokale Regel-Engine (kein externer Call)
    decision_engine: Literal["auto", "systemone", "anthropic", "heuristic"] = "auto"

    # "System One"-Decision-Modelle (kein Text, nur Wahrscheinlichkeiten).
    # Ollama: http://localhost:11434 (Docker: http://ollama:11434), kein Key nötig.
    # TypeSafe Jev: https://api.typesafe.ai + SYSTEMONE_API_KEY, Modell "jev-latest".
    systemone_base_url: str = "http://localhost:11434"
    systemone_api_key: SecretStr | None = None
    systemone_model: str = "tev1:0.8b"
    # Großzügig: Ollama lädt das Modell beim ersten Aufruf (CPU: bis zu ~1 min).
    systemone_timeout_seconds: float = 30.0
    # Ollama hält das Modell so lange im RAM ("30m", oder -1 = dauerhaft). Leer = Server-Einstellung
    # (OLLAMA_KEEP_ALIVE) gilt; leer lassen für TypeSafe.
    systemone_keep_alive: str = "30m"
    # Tev1 hat ~2.048 Tokens Kontext pro Frage und kürzt nie selbst.
    systemone_max_state_chars: int = 3000
    # Kalibriert auf evals/tickets.jsonl: Tev1 vergibt Retouren/Umtausch oft 0.5-0.8,
    # echten Stornos >= 0.96. Mit eigenen Tickets per evals/run_eval.py nachjustieren.
    systemone_cancellation_threshold: float = Field(default=0.9, ge=0.0, le=1.0)
    # Erster Aufruf lädt das Modell (CPU: bis zu ~1-2 min) – eigenes Timeout fürs Vorwärmen.
    systemone_warmup_timeout_seconds: float = 300.0

    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-opus-5-5"
    # Klassifikation braucht kaum Denkaufwand: "low" minimiert Latenz & Kosten.
    anthropic_effort: Literal["low", "medium", "high", "xhigh", "max", ""] = "low"
    anthropic_timeout_seconds: float = 10.0
    anthropic_max_retries: int = 1
    # Serverseitiger Refusal-Fallback (nur für Modelle, die ihn unterstützen).
    anthropic_server_fallbacks: bool = True

    max_ticket_chars: int = 20_000
    max_request_body_bytes: int = Field(default=256 * 1024, ge=8 * 1024, le=10 * 1024 * 1024)
    analysis_sync_wait_seconds: float = Field(default=1.5, ge=0.0, le=30.0)
    analysis_worker_concurrency: int = Field(default=1, ge=1, le=16)
    analysis_max_pending_per_tenant: int = Field(default=100, ge=1, le=10_000)
    analysis_job_lease_seconds: float = Field(default=120.0, gt=0.0)
    analysis_job_max_attempts: int = Field(default=3, ge=1, le=10)
    analysis_job_poll_interval_seconds: float = Field(default=0.2, gt=0.0)
    analysis_job_retention_days: int = Field(default=7, ge=1, le=90)

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
    # NoDecode: Wert kommt als "*" oder "https://a.de,https://b.de", nicht als JSON.
    cors_allow_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["*"])
    api_key_cache_ttl_seconds: float = 15.0
    rate_limit_secret_key_per_minute: int = Field(default=600, ge=1)
    rate_limit_publishable_key_per_minute: int = Field(default=60, ge=1)

    @field_validator("systemone_base_url")
    @classmethod
    def _check_base_url(cls, value: str) -> str:
        value = value.strip()  # z. B. Zeilenumbruch aus Secret-Dateien
        if not value.startswith(("http://", "https://")):
            raise ValueError("SYSTEMONE_BASE_URL muss mit http:// oder https:// beginnen")
        return value.rstrip("/")

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    def asyncpg_connect_options(self) -> tuple[str, dict[str, Any]]:
        """DATABASE_URL -> (asyncpg-kompatible DSN, zusätzliche create_pool-Argumente)."""
        parts = urlsplit(self.database_url)
        params = parse_qsl(parts.query)
        has_root_cert = any(key == "sslrootcert" for key, _ in params)
        options: dict[str, Any] = {}
        kept: list[tuple[str, str]] = []
        for key, value in params:
            if key == "connect_timeout":
                options["timeout"] = float(value)
            elif key == "sslmode" and value == "verify-full" and not has_root_cert:
                # libpq-Semantik ohne Root-Zertifikatsdatei: System-CAs nutzen, Host prüfen.
                options["ssl"] = ssl.create_default_context()
            elif key not in _NON_ASYNCPG_DSN_PARAMS:
                kept.append((key, value))
        cache_size = self.db_statement_cache_size
        if cache_size is None and "-pooler" in (parts.hostname or ""):
            cache_size = 0  # PgBouncer im Transaktionsmodus: keine benannten Statements cachen
        if cache_size is not None:
            options["statement_cache_size"] = cache_size
        scheme = "postgresql" if parts.scheme in {"postgres", "postgresql"} else parts.scheme
        return urlunsplit((scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment)), options

    @property
    def asyncpg_dsn(self) -> str:
        return self.asyncpg_connect_options()[0]

    @property
    def anthropic_enabled(self) -> bool:
        if self.decision_engine not in {"auto", "anthropic"}:
            return False
        return bool(self.anthropic_api_key and self.anthropic_api_key.get_secret_value())

    @property
    def stripe_enabled(self) -> bool:
        return bool(self.stripe_secret_key and self.stripe_secret_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
