"""Tests for application lifespan (startup/shutdown)."""

import asyncio
from unittest.mock import patch

import pytest
from fastapi import FastAPI


async def _run_lifespan(app: FastAPI) -> None:
    """Run the lifespan context manager to completion."""
    from document_anonymizer.api.app import lifespan

    async with lifespan(app):
        pass


class TestLifespan:
    def test_lifespan_calls_get_analyzer(self) -> None:
        """Startup should eagerly load the analyzer engine."""
        from document_anonymizer.api.app import app

        with patch("document_anonymizer.api.dependencies.get_analyzer") as mock:
            asyncio.run(_run_lifespan(app))
            mock.assert_called_once()

    def test_lifespan_propagates_exception(self) -> None:
        """Failed analyzer load must propagate, preventing startup."""
        from document_anonymizer.api.app import app

        with (
            patch(
                "document_anonymizer.api.dependencies.get_analyzer",
                side_effect=RuntimeError("model missing"),
            ),
            pytest.raises(RuntimeError, match="model missing"),
        ):
            asyncio.run(_run_lifespan(app))
