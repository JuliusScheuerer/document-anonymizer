"""Tests for SecurityHeadersMiddleware — request_id context cleanup and caching."""

import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from document_anonymizer.security.middleware import SecurityHeadersMiddleware


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)
    return app


class TestRequestIdContextCleanup:
    def test_request_id_cleaned_after_response(self) -> None:
        """request_id must not leak into structlog context after a normal request."""
        app = _make_app()

        @app.get("/ok")
        async def ok_endpoint(request: Request) -> PlainTextResponse:
            return PlainTextResponse("ok")

        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/ok")
        assert r.status_code == 200

        ctx = structlog.contextvars.get_contextvars()
        assert "request_id" not in ctx

    def test_request_id_cleaned_on_exception(self) -> None:
        """request_id must not leak even when the endpoint raises."""
        app = _make_app()

        @app.get("/boom")
        async def boom_endpoint(request: Request) -> PlainTextResponse:
            msg = "boom"
            raise RuntimeError(msg)

        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/boom")
        assert r.status_code == 500

        ctx = structlog.contextvars.get_contextvars()
        assert "request_id" not in ctx

    def test_response_contains_request_id_header(self) -> None:
        """X-Request-ID header must be present on every response."""
        app = _make_app()

        @app.get("/ping")
        async def ping_endpoint(request: Request) -> PlainTextResponse:
            return PlainTextResponse("pong")

        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/ping")
        assert r.status_code == 200
        assert "X-Request-ID" in r.headers
        assert len(r.headers["X-Request-ID"]) == 36  # UUID4 length


class TestCacheControlBranching:
    def test_static_path_gets_public_cache(self) -> None:
        """Requests under /static/ with 200 status get public caching."""
        app = _make_app()

        @app.get("/static/test.css")
        async def static_endpoint(request: Request) -> PlainTextResponse:
            return PlainTextResponse("body{}", media_type="text/css")

        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/static/test.css")
        assert r.status_code == 200
        assert r.headers["Cache-Control"] == "public, max-age=86400"
        assert "Pragma" not in r.headers

    def test_non_static_path_gets_no_store(self) -> None:
        """Non-static paths must get no-store to prevent PII caching."""
        app = _make_app()

        @app.get("/api/data")
        async def api_endpoint(request: Request) -> PlainTextResponse:
            return PlainTextResponse("data")

        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/api/data")
        assert r.status_code == 200
        assert r.headers["Cache-Control"] == "no-store, no-cache, must-revalidate"
        assert r.headers["Pragma"] == "no-cache"

    def test_static_404_gets_no_store(self) -> None:
        """A 404 under /static/ must not be cached."""
        app = _make_app()

        @app.get("/static/missing.css")
        async def missing_endpoint(request: Request) -> Response:
            return Response("Not Found", status_code=404)

        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/static/missing.css")
        assert r.status_code == 404
        assert r.headers["Cache-Control"] == "no-store, no-cache, must-revalidate"
        assert r.headers["Pragma"] == "no-cache"
