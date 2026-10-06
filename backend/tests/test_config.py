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
