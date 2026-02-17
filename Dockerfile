# ── Builder stage ─────────────────────────────────────
FROM python:3.12-slim-bookworm AS builder

# System deps for python-magic
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv (pinned version)
COPY --from=ghcr.io/astral-sh/uv:0.10.3 /uv /uvx /bin/

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies only
RUN uv sync --frozen --no-dev

# Download spaCy model at build time (air-gappable at runtime)
RUN uv run python -m spacy download de_core_news_lg

# Copy source code
COPY src/ src/

# ── Runtime stage ────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

LABEL org.opencontainers.image.source="https://github.com/JuliusScheuerer/document-anonymizer"
LABEL org.opencontainers.image.description="German PII detection and anonymization"

# System deps for python-magic
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only the virtualenv and source from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

# Run as non-root user
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "document_anonymizer.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
