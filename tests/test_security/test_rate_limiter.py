"""Tests for rate limiter middleware."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import PlainTextResponse

from document_anonymizer.security.rate_limiter import RateLimiterMiddleware


def _create_app(
    requests_per_window: int = 3,
    window_seconds: int = 60,
    trusted_proxies: set[str] | None = None,
) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        RateLimiterMiddleware,
        requests_per_window=requests_per_window,
        window_seconds=window_seconds,
        trusted_proxies=trusted_proxies,
    )

    @app.get("/test")
    async def test_endpoint() -> PlainTextResponse:
        return PlainTextResponse("ok")

    return app


class TestRateLimiter:
    def test_allows_requests_within_limit(self) -> None:
        app = _create_app(requests_per_window=5)
        client = TestClient(app)
        for _ in range(5):
            r = client.get("/test")
            assert r.status_code == 200

    def test_blocks_after_limit(self) -> None:
        app = _create_app(requests_per_window=2)
        client = TestClient(app)
        client.get("/test")
        client.get("/test")
        r = client.get("/test")
        assert r.status_code == 429
        assert "Rate limit" in r.json()["detail"]

    def test_retry_after_header(self) -> None:
        app = _create_app(requests_per_window=1)
        client = TestClient(app)
        client.get("/test")
        r = client.get("/test")
        assert r.status_code == 429
        assert "Retry-After" in r.headers


class TestRateLimiterSpoofing:
    def test_ignores_forwarded_for_from_untrusted_source(self) -> None:
        """X-Forwarded-For from untrusted client should be ignored."""
        app = _create_app(requests_per_window=2)
        client = TestClient(app)

        # Try to bypass by sending spoofed X-Forwarded-For
        for _ in range(2):
            client.get("/test")

        # Third request with spoofed header should still be blocked
        r = client.get(
            "/test",
            headers={"X-Forwarded-For": "1.2.3.4"},
        )
        assert r.status_code == 429

    def test_trusts_forwarded_for_from_trusted_proxy(self) -> None:
        """X-Forwarded-For from trusted proxy should be honored."""
        app = _create_app(
            requests_per_window=2,
            trusted_proxies={"testclient"},
        )
        client = TestClient(app)

        # Two requests from "client A" via proxy
        for _ in range(2):
            client.get(
                "/test",
                headers={"X-Forwarded-For": "10.0.0.1"},
            )

        # Request from "client B" should still work
        r = client.get(
            "/test",
            headers={"X-Forwarded-For": "10.0.0.2"},
        )
        assert r.status_code == 200
