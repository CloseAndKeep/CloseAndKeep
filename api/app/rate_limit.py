"""Sliding-window rate limits.

Uses an in-process store by default (fine for a single uvicorn worker). When
``REDIS_URL`` is set, counters are shared across workers and instances via Redis.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .config import settings

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """In-process sliding-window limiter (not shared across processes)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def reset(self) -> None:
        """Clear all counters (tests only)."""
        with self._lock:
            self._hits.clear()

    def check(self, key: str, *, limit: int, window_seconds: float) -> None:
        if limit <= 0:
            return
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Try again shortly.",
                    headers={"Retry-After": str(max(1, int(window_seconds)))},
                )
            bucket.append(now)


class RedisSlidingWindowRateLimiter:
    """Shared sliding-window limiter backed by a Redis sorted set."""

    def __init__(self, client: object) -> None:
        self._client = client

    def reset(self) -> None:
        # Tests use the in-memory limiter; Redis reset is a no-op safety net.
        return

    def check(self, key: str, *, limit: int, window_seconds: float) -> None:
        if limit <= 0:
            return
        now = time.time()
        cutoff = now - window_seconds
        redis_key = f"cak:rl:{key}"
        # Sliding window via sorted set. Slight overshoot under concurrency is OK.
        pipe = self._client.pipeline()  # type: ignore[attr-defined]
        pipe.zremrangebyscore(redis_key, 0, cutoff)
        pipe.zcard(redis_key)
        _removed, count = pipe.execute()
        if count >= limit:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Try again shortly.",
                headers={"Retry-After": str(max(1, int(window_seconds)))},
            )
        pipe = self._client.pipeline()  # type: ignore[attr-defined]
        pipe.zadd(redis_key, {f"{now}": now})
        pipe.expire(redis_key, max(1, int(window_seconds) + 1))
        pipe.execute()


class RateLimiter:
    """Facade that prefers Redis when configured, else in-process counters."""

    def __init__(self) -> None:
        self._memory = SlidingWindowRateLimiter()
        self._redis: RedisSlidingWindowRateLimiter | None = None
        if settings.redis_url:
            try:
                import redis

                client = redis.from_url(settings.redis_url, decode_responses=True)
                client.ping()
                self._redis = RedisSlidingWindowRateLimiter(client)
                logger.info("Rate limits are shared via Redis.")
            except Exception:
                logger.exception(
                    "REDIS_URL is set but Redis is unavailable; falling back to "
                    "in-process rate limits (not shared across workers)."
                )

    def reset(self) -> None:
        self._memory.reset()
        if self._redis:
            self._redis.reset()

    def check(self, key: str, *, limit: int, window_seconds: float) -> None:
        backend = self._redis or self._memory
        backend.check(key, limit=limit, window_seconds=window_seconds)


limiter = RateLimiter()


def client_ip(request: Request, *, trust_proxy: bool | None = None) -> str:
    """Return the client IP for rate limiting.

    ``X-Forwarded-For`` is only used when ``trust_proxy`` is true (or
    ``settings.trust_proxy``). Otherwise any client could spoof the header.
    """
    use_proxy = settings.trust_proxy if trust_proxy is None else trust_proxy
    if use_proxy:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # First hop is the original client when behind a trusted proxy.
            return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
