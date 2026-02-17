"""Structured audit logging for compliance.

All audit events are emitted as structured JSON for machine parsing,
traceability, and regulatory compliance.
"""

import logging
import os

import structlog

_LOG_LEVEL_MAP: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def configure_logging() -> None:
    """Configure structlog for structured JSON audit logging."""
    log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_level = _LOG_LEVEL_MAP.get(log_level_name, logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a named audit logger.

    Args:
        name: Logger name, typically the module path.

    Returns:
        A bound structlog logger with the given name.
    """
    return structlog.get_logger(name)  # type: ignore[no-any-return]
