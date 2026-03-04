"""Tests for rate limiter middleware."""

import pytest
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


class TestRateLimiterMaxIPs:
    def test_new_ip_rejected_when_max_tracked_ips_reached(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When _MAX_TRACKED_IPS is reached, new IPs should get 429."""
        import document_anonymizer.security.rate_limiter as rl_mod

        monkeypatch.setattr(rl_mod, "_MAX_TRACKED_IPS", 1)

        app = _create_app(
            requests_per_window=100,
            window_seconds=60,
            trusted_proxies={"testclient"},
        )
        client = TestClient(app)

        # First request from IP "10.0.0.1" fills the single slot
        r = client.get(
            "/test",
            headers={"X-Forwarded-For": "10.0.0.1"},
        )
        assert r.status_code == 200

        # Second request from a different IP should be rejected
        r = client.get(
            "/test",
            headers={"X-Forwarded-For": "10.0.0.2"},
        )
        assert r.status_code == 429


class TestRateLimiterEviction:
    def test_stale_ips_evicted_after_window(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IPs should be cleaned from _requests after window expires."""
        import document_anonymizer.security.rate_limiter as rl_mod

        fake_time = 1000.0

        def mock_monotonic() -> float:
            return fake_time

        monkeypatch.setattr(rl_mod.time, "monotonic", mock_monotonic)

        app = _create_app(requests_per_window=5, window_seconds=10)
        client = TestClient(app)

        # Make a request at t=1000
        r = client.get("/test")
        assert r.status_code == 200

        # Advance time past the window
        fake_time = 1011.0

        # Next request triggers cleanup; stale IP should be evicted
        r = client.get("/test")
        assert r.status_code == 200

        # Access the middleware to check internal state
        middleware = app.middleware_stack
        # Walk through middleware wrappers to find our RateLimiterMiddleware
        rl = None
        obj = middleware
        while obj is not None:
            if isinstance(obj, rl_mod.RateLimiterMiddleware):
                rl = obj
                break
            obj = getattr(obj, "app", None)

        assert rl is not None
        # After cleanup at t=1011, no timestamps from t=1000 should remain
        for _ip, timestamps in rl._requests.items():
            for ts in timestamps:
                assert ts > 1001.0, "Stale timestamp was not evicted"


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
