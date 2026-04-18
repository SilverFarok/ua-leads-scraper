"""Simple request pacing helper."""

from __future__ import annotations

import time


class RateLimiter:
    """Enforce a minimum delay between requests."""

    def __init__(self, delay_seconds: float) -> None:
        self._delay_seconds = max(delay_seconds, 0.0)
        self._last_call = 0.0

    def wait(self) -> None:
        """Sleep if the previous call was too recent."""
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self._delay_seconds:
            time.sleep(self._delay_seconds - elapsed)
        self._last_call = time.monotonic()
