<p align="center">
  <strong>Document Anonymizer</strong><br>
  Privacy-first German PII detection and document redaction
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &middot;
  <a href="#architecture">Architecture</a> &middot;
  <a href="#tech-stack">Tech Stack</a> &middot;
  <a href="#development">Development</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12-blue" alt="Python 3.12">
  <img src="https://img.shields.io/badge/fastapi-0.129-teal" alt="FastAPI">
  <img src="https://img.shields.io/badge/presidio-2.2-0078D4" alt="Presidio">
  <img src="https://img.shields.io/badge/spaCy-3.7-09A3D5" alt="spaCy">
  <img src="https://img.shields.io/badge/PyMuPDF-1.27-red" alt="PyMuPDF">
  <img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="MIT License">
</p>

---

Detect personally identifiable information in German text and PDF files using seven custom recognizers plus spaCy NER. Anonymize with five strategies (replace, fake, mask, hash, redact) and perform **physical PDF redaction** that removes text from the content stream — not cosmetic overlay. Built for environments where data protection matters: financial regulation (BaFin), healthcare, legal, and public sector.

## Quick Start

```bash
git clone git@github.com:JuliusScheuerer/document-anonymizer.git
cd document-anonymizer
uv sync --dev

uv run uvicorn document_anonymizer.api.app:app --reload
# http://localhost:8000      → Web UI
# http://localhost:8000/docs → OpenAPI docs
```

**Docker:**
```bash
docker compose up -d --build
# Health check: curl http://localhost:8000/health
```

The Docker image downloads the spaCy model at build time (~500 MB), so the container runs fully offline.

## Usage

The HTMX-powered frontend provides a complete workflow: paste text or upload a file (TXT/PDF), adjust the confidence threshold, review detected entities with highlighted annotations, choose an anonymization strategy, and download the result.

```bash
# Detect PII entities
curl -s -X POST http://localhost:8000/api/detect \
  -H "Content-Type: application/json" \
  -d '{"text": "Herr Max Mustermann, IBAN DE89 3704 0044 0532 0130 00"}' | jq

# Anonymize text
curl -s -X POST http://localhost:8000/api/anonymize \
  -H "Content-Type: application/json" \
  -d '{"text": "Max Mustermann, Steuer-ID 12345679811", "strategy": "replace"}' | jq
```

Full API documentation at `/docs` (Swagger UI) and `/redoc`.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  Web UI (HTMX + Jinja2)        REST API (/api)       │
│  Upload → Detect → Review → Anonymize / Download      │
├──────────────────────────────────────────────────────┤
│  Security Middleware                                   │
│  CSP · Rate Limiter · File Validation · Audit Log     │
├────────────────────────┬─────────────────────────────┤
│  Detection Engine      │  Anonymization Engine        │
│  Presidio + spaCy NER  │  Replace · Mask · Hash       │
│  7 German recognizers  │  Fake (de_DE) · Redact       │
├────────────────────────┴─────────────────────────────┤
│  Document Layer                                       │
│  Text Handler · PDF Handler (PyMuPDF physical redact) │
└──────────────────────────────────────────────────────┘
```

**Key properties:** Zero persistence (all in-memory), air-gappable (no runtime network calls), PII-free audit logging (entity counts only, GDPR Art. 5(1)(c)), defense-in-depth validation (magic bytes, PDF structure checks, size limits).

### German PII Recognizers

| Recognizer | Entity Type | Detection Method |
|:-----------|:------------|:-----------------|
| IBAN | `DE_IBAN` | Pattern match + ISO 7064 Mod 97-10 checksum validation |
| Tax ID | `DE_TAX_ID` | Steuer-ID (11-digit) + Steuernummer (regional format) with digit distribution check |
| Phone | `DE_PHONE` | International (+49), domestic (0xxx), and mobile formats with context boosting |
| ID Card | `DE_ID_CARD` | Restricted alphanumeric charset + check digit (weights 7, 3, 1) |
| Handelsregister | `DE_HANDELSREGISTER` | HRA/HRB + number with Registergericht context boosting |
| Address | `DE_ADDRESS` | 5-digit PLZ + street patterns (Straße, Weg, Platz, Allee) |
| Date | `DE_DATE` | DD.MM.YYYY with birth context boosting (geboren, Geburtsdatum) |

### Anonymization Strategies

| Strategy | Output | Example |
|:---------|:-------|:--------|
| **Replace** | Entity type label | `Max Mustermann` → `[PERSON]` |
| **Fake** | Realistic German synthetic data | `Max Mustermann` → `Hans Jürgen Ladeck` |
| **Mask** | Partial character masking | `DE89 3704 0044...` → `**** **** ****...` |
| **Hash** | SHA-256 pseudonymization | `Max Mustermann` → `b8a0a89e...` |
| **Redact** | Complete removal | `Max Mustermann` → ` ` |

### Security

| Layer | Implementation |
|:------|:---------------|
| Input validation | Magic bytes via libmagic, PDF structure check, 10 MB size limit |
| XSS prevention | Full HTML escaping before markup insertion, strict CSP |
| Security headers | CSP, X-Frame-Options DENY, HSTS, no-referrer, Permissions-Policy |
| Rate limiting | Sliding window per IP, X-Forwarded-For spoofing protection |
| Audit trail | Structured JSON logging with request ID correlation, PII-free |
| PDF redaction | Physical text removal from content stream + metadata scrubbing |
| Static analysis | Bandit, ruff security rules (S prefix), Semgrep in CI |

See [`docs/security.md`](docs/security.md) for the full security architecture documentation.

## Tech Stack

| Component | Technology |
|:----------|:-----------|
| PII Detection | [Microsoft Presidio](https://github.com/microsoft/presidio) + [spaCy](https://spacy.io/) `de_core_news_lg` |
| PDF Redaction | [PyMuPDF](https://pymupdf.readthedocs.io/) (physical redaction, not cosmetic) |
| Web Framework | [FastAPI](https://fastapi.tiangolo.com/) |
| Frontend | [HTMX](https://htmx.org/) + Jinja2 (vendored, no CDN) |
| Synthetic Data | [Faker](https://faker.readthedocs.io/) `de_DE` locale |
| File Validation | python-magic (libmagic) |
| Logging | [structlog](https://www.structlog.org/) (structured JSON) |
| Quality | ruff, mypy (strict), bandit, Hypothesis, 92% test coverage |

## Development

```bash
make check              # Lint + typecheck + unit tests
make test               # Unit tests (90% coverage gate)
make test-integration   # API round-trip tests
make test-e2e           # PDF redaction verification
make test-property      # Hypothesis fuzzing on recognizers
make security           # Bandit security scan
make check-compliance   # Full compliance suite
```

The GitHub Actions CI runs lint, typecheck, and security scanning in parallel, followed by the test suite and compliance checks. All steps use pinned dependency versions (`uv sync --frozen`).

## License

[MIT](LICENSE)
