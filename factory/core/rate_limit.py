"""Sliding-window rate limit counter. Pure Python, no ASGI dependency."""

import time


class RateLimitCounter:
    """Sliding-window counter for a single rate-limit bucket."""

    def __init__(self, limit: int, window: int = 60):
        self.limit = limit
        self.window = window
        self._timestamps: list[float] = []

    def allow(self, now: float | None = None) -> bool:
        if now is None:
            now = time.time()
        cutoff = now - self.window
        self._timestamps = [t for t in self._timestamps if t > cutoff]
        if len(self._timestamps) >= self.limit:
            return False
        self._timestamps.append(now)
        return True
