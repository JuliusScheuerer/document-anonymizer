# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public issue.
2. Open a [private security advisory](https://github.com/JuliusScheuerer/document-anonymizer/security/advisories/new) on this repository.
3. Include steps to reproduce if possible.

You should receive an acknowledgment within 48 hours.

## Supported Versions

| Version | Supported |
|:--------|:----------|
| 0.1.x   | Yes       |

## Security Measures

### Static Analysis

- **Ruff** with bandit rules (`S` prefix) for inline security checks
- **Bandit** for dedicated security scanning
- **Semgrep** (auto config) in CI pipeline
- **Pre-commit hooks** enforce all checks before every commit

### Runtime Protection

- Strict Content Security Policy (CSP) headers
- Rate limiting with X-Forwarded-For spoofing protection
- Input validation via magic bytes (not file extensions)
- Physical PDF redaction (text removed from content stream)
- Zero persistence architecture — no data stored to disk

### Audit & Compliance

- Structured JSON audit logging via `structlog`
- Request ID correlation across all log entries
- PII-free logging (entity counts only, never content)
- Property-based testing via Hypothesis
- End-to-end redaction verification tests

## Dependency Management

Dependencies are managed via `uv` with pinned versions in `uv.lock`.

```bash
make security    # Run Bandit security scan
make check-compliance  # Full compliance suite
```
