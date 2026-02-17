.DEFAULT_GOAL := help
.PHONY: help lint typecheck test check format clean

PYTEST_BASE := uv run pytest -p no:faker --randomly-dont-reset-seed
PYTEST_NO_MARKERS := $(PYTEST_BASE) --override-ini="addopts=-ra --strict-markers --strict-config -p no:faker --randomly-dont-reset-seed"

## ── Always Available ──────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

lint: ## Run linter (ruff)
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

format: ## Format code
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

typecheck: ## Run type checker (mypy)
	uv run mypy src/

test: ## Run unit tests
	$(PYTEST_BASE) --cov

check: lint typecheck test ## Run all checks (lint + typecheck + test)

clean: ## Remove build artifacts
	rm -rf dist/ build/ .eggs/ *.egg-info .mypy_cache .ruff_cache .pytest_cache htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

## ── Tier 2: Deployable ────────────────────────────────

.PHONY: security test-integration docker-up docker-down check-all

security: ## Run security checks (bandit)
	uv run bandit -r src/ -c pyproject.toml

test-integration: ## Run integration tests
	$(PYTEST_NO_MARKERS) tests/integration/ --cov

docker-up: ## Start Docker containers
	docker compose up -d --build

docker-down: ## Stop Docker containers
	docker compose down

check-all: check security test-integration ## Run all checks including security & integration

## ── Tier 3: Compliance ────────────────────────────────

.PHONY: test-e2e test-property audit check-compliance

test-e2e: ## Run end-to-end tests
	$(PYTEST_NO_MARKERS) tests/e2e/

test-property: ## Run property-based tests
	$(PYTEST_NO_MARKERS) tests/property/

audit: ## Run compliance audit checks
	uv run bandit -r src/ -c pyproject.toml --severity-level medium
	@echo "Audit logging verification..."
	@uv run python -c "from document_anonymizer.audit.logging import get_logger; print('Audit logger OK')"

check-compliance: check security test-integration test-e2e test-property audit ## Full compliance check suite
