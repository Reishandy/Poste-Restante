import asyncio
import time
from collections import defaultdict

from src.config import settings


class InMemoryRateLimiter:
    """Sliding-window in-memory rate limiter with automatic stale IP eviction."""

    def __init__(self):
        self._history: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(self, client_ip: str) -> tuple[bool, int]:
        """
        Checks whether client_ip has exceeded settings.RATE_LIMIT_REQUESTS.
        Returns: (is_allowed, retry_after_seconds)
        """
        now = time.monotonic()
        max_requests = settings.RATE_LIMIT_REQUESTS
        window_seconds = settings.RATE_LIMIT_WINDOW_SECONDS
        cutoff = now - window_seconds

        async with self._lock:
            # Retain only timestamps within the current window
            timestamps = [t for t in self._history[client_ip] if t > cutoff]

            if len(timestamps) >= max_requests:
                oldest = timestamps[0]
                retry_after = max(1, int(window_seconds - (now - oldest)))
                self._history[client_ip] = timestamps
                return False, retry_after

            timestamps.append(now)
            self._history[client_ip] = timestamps

            # Prevent memory bloat from inactive clients
            if len(self._history) > 5000:
                self._purge_stale_ips(cutoff)

            return True, 0

    def _purge_stale_ips(self, cutoff: float) -> None:
        dead_ips = [
            ip
            for ip, stamps in self._history.items()
            if not stamps or stamps[-1] <= cutoff
        ]
        for ip in dead_ips:
            del self._history[ip]

    def reset(self) -> None:
        """Clears all tracking history (primarily used in tests)."""
        self._history.clear()


limiter = InMemoryRateLimiter()
