"""Security middleware: CSP, headers, request ID tracking."""

import secrets
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_STATIC_PATH_PREFIX = "/static/"
_SWAGGER_CDN = "https://cdn.jsdelivr.net"
_SWAGGER_PATHS = ("/docs", "/openapi.json")

# Number of random bytes for CSP nonce (16 bytes = 128 bits of entropy)
_CSP_NONCE_BYTES = 16


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Generate unique request ID for audit trail
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Generate per-request CSP nonce for inline scripts
        csp_nonce = secrets.token_urlsafe(_CSP_NONCE_BYTES)
        request.state.csp_nonce = csp_nonce

        # Bind request_id to structlog context for all downstream logging
        structlog.contextvars.bind_contextvars(request_id=request_id)

        try:
            response = await call_next(request)

            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
            # Swagger UI (/docs) loads JS/CSS from cdn.jsdelivr.net and
            # uses inline scripts that don't carry our nonce. Relax CSP
            # for the docs path only — it serves no user data.
            is_swagger = request.url.path in _SWAGGER_PATHS
            if is_swagger:
                response.headers["Content-Security-Policy"] = (
                    "default-src 'self'; "
                    f"script-src 'self' 'unsafe-inline' {_SWAGGER_CDN}; "
                    f"style-src 'self' 'unsafe-inline' {_SWAGGER_CDN}; "
                    f"img-src 'self' data: {_SWAGGER_CDN}; "
                    "font-src 'self'; "
                    "frame-ancestors 'none'; "
                    "base-uri 'self'; "
                    "form-action 'self'"
                )
            else:
                response.headers["Content-Security-Policy"] = (
                    "default-src 'self'; "
                    f"script-src 'self' 'nonce-{csp_nonce}'; "
                    "style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data:; "
                    "font-src 'self'; "
                    "frame-ancestors 'none'; "
                    "base-uri 'self'; "
                    "form-action 'self'"
                )
            response.headers["Permissions-Policy"] = (
                "camera=(), microphone=(), geolocation=()"
            )
            # SECURITY INVARIANT: Only successful /static/ responses may be
            # cached.  All other responses may contain PII and MUST use
            # no-store.  If you add routes under /static/, ensure they
            # serve no user data.
            is_cacheable_static = (
                request.url.path.startswith(_STATIC_PATH_PREFIX)
                and response.status_code == 200
            )
            if is_cacheable_static:
                response.headers["Cache-Control"] = "public, max-age=86400"
            else:
                response.headers["Cache-Control"] = (
                    "no-store, no-cache, must-revalidate"
                )
                response.headers["Pragma"] = "no-cache"
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
