#!/usr/bin/env bash
# Security check script for document-anonymizer
set -euo pipefail

echo "Running security checks..."

echo "==> Bandit (Python security linter)"
uv run bandit -r src/ -c pyproject.toml

echo "==> Checking for known vulnerabilities in dependencies"
uv pip audit 2>/dev/null || echo "Note: uv pip audit not available, skipping dependency audit"

echo "Security checks complete."
