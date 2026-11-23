"""In-process sliding-window rate limiter.

Adequate for a single API process (the research deployment). For multiple replicas, replace the
backend with a shared store (e.g. Redis) — the interface is intentionally tiny.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window: float) -> tuple[bool, float]:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= limit:
                return False, window - (now - q[0])
            q.append(now)
            return True, 0.0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    # Only trust X-Forwarded-For when explicitly deployed behind a proxy that sets it
    # (uvicorn --proxy-headers rewrites request.client for trusted proxies).
    return request.client.host if request.client else "unknown"


def enforce(request: Request, bucket: str, limit: int, window: int, identity: str | None = None) -> None:
    key = f"{bucket}:{identity or client_ip(request)}"
    ok, retry = limiter.check(key, limit, window)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please retry later.",
            headers={"Retry-After": str(max(1, int(retry) + 1))},
        )
