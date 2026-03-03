# CLAUDE.md — Document Anonymizer

## Project Overview

Privacy-first document anonymization tool for German PII detection and redaction.
Built with FastAPI + Microsoft Presidio + spaCy, using HTMX for the web frontend.

## Tech Stack

- **Python 3.12+**, FastAPI, Uvicorn
- **Presidio** (analyzer + anonymizer) with spaCy `de_core_news_lg` for German NER
- **PyMuPDF (fitz)** for physical PDF redaction (not cosmetic overlay)
- **HTMX + Jinja2** for the web UI (vendored, no CDN)
- **structlog** for PII-free structured JSON audit logging
- **Docker** with read-only filesystem, non-root user, resource limits

## Development Commands

```bash
uv sync --dev                  # Install all dependencies
make check                     # Lint + typecheck + unit tests (90% coverage gate)
make test                      # Unit tests only
make test-integration          # API round-trip tests
make test-e2e                  # PDF redaction e2e tests
make test-property             # Hypothesis fuzzing on recognizers
make security                  # Bandit security scan
make check-compliance          # Full suite: check + security + integration + e2e + property
```

## Architecture

```
src/document_anonymizer/
├── api/           # REST API (FastAPI router, Pydantic schemas, DI)
├── anonymization/ # Strategy engine (replace, fake, mask, hash, redact)
├── detection/     # Presidio + 7 custom German recognizers
├── document/      # Text and PDF handlers
├── security/      # Middleware (CSP, rate limiter, file validation)
├── audit/         # structlog configuration
├── web/           # HTMX routes, Jinja2 templates, static assets
└── health.py      # Health check
```

## Key Conventions

- **Zero persistence**: All data is request-scoped, in-memory only. No database, no file storage.
- **PII-free logging**: Never log detected PII content. Only log entity counts, types, and timing.
- **Physical PDF redaction**: Use `add_redact_annot()` + `apply_redactions()` — removes text from content stream.
- **German locale**: All recognizers, fake data, and UI text target German (de_DE).
- **Strict typing**: mypy strict mode. All new code must be fully typed.
- **Security headers**: CSP, X-Frame-Options, HSTS, no-referrer on all responses.
- **Input validation**: Magic bytes for file type (not extension), Pydantic for API schemas.

## Code Style

- **Formatter/Linter**: Ruff (line length 88, target Python 3.12)
- **Rule sets**: E, W, F, I, N, UP, B, SIM, S (bandit), T20, PTH, LOG, TRY, A, C4, RUF, ERA, ARG, TCH
- **Tests**: pytest with 90% coverage gate. Markers: `integration`, `e2e`, `property`
- **Test ignores**: `S101` (assert), `ARG001/ARG002` (unused args) allowed in tests

## Adding a New Recognizer

1. Create `src/document_anonymizer/detection/recognizers/german_<name>.py`
2. Inherit from `PatternRecognizer`, define patterns with context words
3. Register in `detection/recognizers/__init__.py`
4. Add Faker generator mapping in `anonymization/operators.py` if using `fake` strategy
5. Add tests in `tests/test_detection/test_german_<name>.py`

## Running Locally

```bash
uv run uvicorn document_anonymizer.api.app:app --reload
# Web UI:  http://localhost:8000
# API docs: http://localhost:8000/docs
# Health:  http://localhost:8000/health
```
