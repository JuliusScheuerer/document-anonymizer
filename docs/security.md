# Security Architecture

## Zero-Persistence Design

All document processing occurs in-memory within a single HTTP request. No data is written to disk, cached, or stored in any database. After the response is sent, the garbage collector frees all data.

**Why this matters**: In BaFin-regulated environments, data minimization is a compliance requirement. Zero persistence means there's no data store to protect, no retention policy to enforce, and no breach surface for stored documents.

## Physical vs. Cosmetic PDF Redaction

### The Problem

Most PDF "redaction" tools apply **cosmetic redaction**: they draw a black rectangle over the text. The original text remains in the PDF content stream and can be extracted by:
- Copy-pasting from the "redacted" area
- Using `pdftotext` or similar extraction tools
- Opening the PDF in a hex editor

This is a well-documented vulnerability. Notable failures include US DOJ court filings, NSA documents, and corporate legal submissions.

### Our Approach

We use PyMuPDF's `add_redact_annot()` + `apply_redactions()`, which:
1. Marks text regions for redaction
2. Physically removes the text from the PDF content stream
3. Replaces the area with an opaque fill
4. The original text is irrecoverable

Additionally, we call `doc.set_metadata({})` to scrub all document metadata (author, title, creator, etc.) and save with `garbage=4` to remove unreferenced objects.

### Verification

Our E2E tests verify physical redaction by:
1. Creating a PDF with known PII text
2. Running the redaction pipeline
3. Extracting text from the redacted PDF
4. Asserting that the PII text is no longer present

## Input Validation

### Magic Bytes, Not Extensions

File type validation uses `python-magic` (libmagic) to detect MIME types from file content, not from the file extension. This prevents the classic attack of renaming a malicious file (e.g., `.exe` → `.pdf`).

### Allowed Types

Only `text/plain` and `application/pdf` are accepted. All other MIME types are rejected.

### Size Limits

Maximum file size is 10 MB by default, configurable. Empty files are rejected.

### PDF Structure Validation

Beyond MIME type checking, PDF files undergo structural validation:
- Must start with `%PDF` header
- Must contain `%%EOF` marker

## Security Headers

All responses include:

| Header | Value | Purpose |
|--------|-------|---------|
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'; ...` | Prevents XSS, data exfiltration |
| `X-Content-Type-Options` | `nosniff` | Prevents MIME type confusion |
| `X-Frame-Options` | `DENY` | Prevents clickjacking |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Enforces HTTPS |
| `Referrer-Policy` | `no-referrer` | Prevents URL leakage |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Disables unnecessary APIs |
| `X-Request-ID` | UUID | Audit trail correlation |

## Rate Limiting

In-memory sliding window rate limiter per client IP. Default: 60 requests per 60-second window. Respects `X-Forwarded-For` for proxied deployments.

## Audit Logging

Structured JSON logging via structlog. All audit events include:
- Request ID
- Timestamp (ISO 8601)
- Entity type counts (e.g., "found 3 PERSON, 1 IBAN")
- Processing time
- Strategy used

**Critical**: PII content is NEVER logged. Only entity types and counts. This aligns with GDPR Art. 5(1)(c) — data minimization.

## Air-Gap Capability

The application makes zero external network calls at runtime:
- spaCy German model is downloaded at Docker build time
- HTMX is vendored (no CDN)
- No telemetry, no analytics, no external API calls
- Can run in a network-isolated environment
