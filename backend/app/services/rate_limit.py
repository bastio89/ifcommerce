"""Token-Bucket-Rate-Limiter pro API-Key (In-Process).

Für horizontale Skalierung mit vielen Replikas gegen eine Redis-Implementierung
mit identischem Interface austauschen.
"""

from __future__ import annotations

import math
import time
from collections import OrderedDict
from dataclasses import dataclass


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated_at: float


class TokenBucketRateLimiter:
    def __init__(self, *, max_buckets: int = 50_000) -> None:
        self._buckets: OrderedDict[str, _Bucket] = OrderedDict()
        self._max_buckets = max_buckets

    def acquire(self, key: str, *, per_minute: int) -> tuple[bool, int]:
        """Gibt (erlaubt, retry_after_sekunden) zurück."""
        capacity = float(per_minute)
        refill_per_second = per_minute / 60.0
        now = time.monotonic()

        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _Bucket(tokens=capacity, updated_at=now)
            self._buckets[key] = bucket
        else:
            elapsed = now - bucket.updated_at
            bucket.tokens = min(capacity, bucket.tokens + elapsed * refill_per_second)
            bucket.updated_at = now
        self._buckets.move_to_end(key)
        while len(self._buckets) > self._max_buckets:
            self._buckets.popitem(last=False)

        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True, 0
        return False, max(1, math.ceil((1.0 - bucket.tokens) / refill_per_second))
