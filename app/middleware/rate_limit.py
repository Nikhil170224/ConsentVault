"""In-memory rate limiter with a clean interface (swap for Redis later)."""
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimiter(ABC):
    @abstractmethod
    def allow(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        raise NotImplementedError


class InMemoryRateLimiter(RateLimiter):
    def __init__(self):
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        now = time.monotonic()
        bucket = self._hits[key]
        while bucket and bucket[0] <= now - window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()


limiter = InMemoryRateLimiter()


def rate_limit(limit: int):
    def dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        key = f"{request.url.path}:{client}"
        if not limiter.allow(key, limit):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

    return dependency
