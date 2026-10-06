import pytest

from app.config import Settings


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("*", ["*"]),
        ("https://a.de, https://b.de", ["https://a.de", "https://b.de"]),
    ],
)
def test_cors_origins_from_env(monkeypatch: pytest.MonkeyPatch, raw: str, expected: list[str]) -> None:
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", raw)
    assert Settings().cors_allow_origins == expected


def test_prisma_only_dsn_params_are_stripped() -> None:
    settings = Settings(database_url="postgres://u:p@db:5432/app?schema=public&sslmode=require&connection_limit=5")
    assert settings.asyncpg_dsn == "postgresql://u:p@db:5432/app?sslmode=require"


def test_anthropic_only_with_key_and_matching_mode() -> None:
    assert not Settings(anthropic_api_key=None).anthropic_enabled
    assert not Settings(anthropic_api_key="sk-ant-x", decision_engine="heuristic").anthropic_enabled
    assert not Settings(anthropic_api_key="sk-ant-x", decision_engine="systemone").anthropic_enabled
    assert Settings(anthropic_api_key="sk-ant-x", decision_engine="auto").anthropic_enabled


def test_neon_url_is_made_asyncpg_compatible() -> None:
    url = (
        "postgresql://u:p@ep-cool-123-pooler.eu-central-1.aws.neon.tech/neondb"
        "?sslmode=require&channel_binding=require&connect_timeout=15"
    )
    dsn, options = Settings(database_url=url).asyncpg_connect_options()
    assert dsn.endswith("/neondb?sslmode=require")  # channel_binding bricht asyncpg
    assert options == {"timeout": 15.0, "statement_cache_size": 0}  # Pooler -> kein Statement-Cache


def test_verify_full_uses_system_ca_context() -> None:
    import ssl

    dsn, options = Settings(
        database_url="postgresql://u:p@db.example/app?sslmode=verify-full"
    ).asyncpg_connect_options()
    assert "sslmode" not in dsn
    assert isinstance(options["ssl"], ssl.SSLContext)
    assert options["ssl"].check_hostname is True


def test_systemone_base_url_is_validated() -> None:
    assert Settings(systemone_base_url="http://ollama:11434/\n").systemone_base_url == "http://ollama:11434"
    with pytest.raises(ValueError, match="http"):
        Settings(systemone_base_url="ollama:11434")
