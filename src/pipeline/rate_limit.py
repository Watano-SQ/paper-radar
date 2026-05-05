from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(slots=True)
class RateLimiter:
    delay_seconds: float = 0.0
    _last_request: float | None = None

    def wait(self) -> None:
        if self.delay_seconds <= 0:
            self._last_request = time.monotonic()
            return
        now = time.monotonic()
        if self._last_request is not None:
            elapsed = now - self._last_request
            remaining = self.delay_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_request = time.monotonic()
