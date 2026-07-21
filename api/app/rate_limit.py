"""Simple in-process sliding-window rate limits.

Good enough for a single API instance. Swap the store for Redis if you run
multiple workers that must share counters.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .config import settings


class SlidingWindowRateLimiter:
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


limiter = SlidingWindowRateLimiter()


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
