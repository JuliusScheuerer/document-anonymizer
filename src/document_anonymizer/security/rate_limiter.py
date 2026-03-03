"""In-memory sliding window rate limiter with async safety."""

import asyncio
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Maximum number of tracked IPs to prevent unbounded memory growth
_MAX_TRACKED_IPS = 10_000


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Sliding window rate limiter per client IP.

    Tracks request timestamps per IP and rejects requests that exceed
    the configured rate within the window period. Uses an asyncio lock
    to prevent TOCTOU races under concurrent requests.
    """

    def __init__(
        self,
        app: object,
        requests_per_window: int = 60,
        window_seconds: int = 60,
        trusted_proxies: set[str] | None = None,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.trusted_proxies = trusted_proxies or set()
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, only trusting X-Forwarded-For from known proxies."""
        client_host = request.client.host if request.client else "unknown"

        forwarded = request.headers.get("x-forwarded-for")
        if forwarded and client_host in self.trusted_proxies:
            return forwarded.split(",")[0].strip()

        return client_host

    def _clean_old_requests(self, now: float) -> None:
        """Remove timestamps outside the current window and evict stale IPs."""
        cutoff = now - self.window_seconds
        stale_ips: list[str] = []

        for ip, timestamps in self._requests.items():
            self._requests[ip] = [ts for ts in timestamps if ts > cutoff]
            if not self._requests[ip]:
                stale_ips.append(ip)

        for ip in stale_ips:
            del self._requests[ip]

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        client_ip = self._get_client_ip(request)
        now = time.monotonic()

        async with self._lock:
            self._clean_old_requests(now)

            # Reject if tracked IPs exceed cap (defense against distributed attacks)
            if (
                client_ip not in self._requests
                and len(self._requests) >= _MAX_TRACKED_IPS
            ):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again later."},
                    headers={"Retry-After": str(self.window_seconds)},
                )

            if len(self._requests[client_ip]) >= self.requests_per_window:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again later."},
                    headers={"Retry-After": str(self.window_seconds)},
                )

            self._requests[client_ip].append(now)

        return await call_next(request)
