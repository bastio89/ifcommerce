"""PostgreSQL-backed token bucket shared by all backend processes and replicas."""

from __future__ import annotations

import math

import asyncpg

_ACQUIRE_SQL = """
INSERT INTO api_rate_limit_buckets (api_key_id, tokens, updated_at)
VALUES ($1::uuid, $2::double precision - 1.0, clock_timestamp())
ON CONFLICT (api_key_id) DO UPDATE
SET tokens = LEAST(
        $2::double precision,
        api_rate_limit_buckets.tokens
            + GREATEST(
                0.0,
                EXTRACT(EPOCH FROM (clock_timestamp() - api_rate_limit_buckets.updated_at))
            ) * $3::double precision
    ) - 1.0,
    updated_at = clock_timestamp()
RETURNING tokens
"""


class DatabaseTokenBucketRateLimiter:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def acquire(self, key: str, *, per_minute: int) -> tuple[bool, int]:
        """Gibt (erlaubt, retry_after_sekunden) zurück."""
        refill_per_second = per_minute / 60.0
        tokens = await self._pool.fetchval(_ACQUIRE_SQL, key, per_minute, refill_per_second)
        if tokens >= 0.0:
            return True, 0
        return False, max(1, math.ceil(-tokens / refill_per_second))
