.DEFAULT_GOAL := help
.PHONY: help install run format lint test check

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies with uv
	uv sync

run: ## Start a local Home Assistant with this integration on http://localhost:8123
	@ln -sfn ../custom_components config/custom_components
	uv run hass --config config --debug

format: ## Auto-fix lint issues and format the code
	uv run ruff check --fix .
	uv run ruff format .

lint: ## Run ruff (lint and format check) and mypy
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy custom_components scripts

test: ## Run tests with coverage (fails under 95%)
	uv run pytest --cov=custom_components.cloudflare_workers_ai --cov-report=term-missing --cov-fail-under=95

check: lint test ## Run lint and tests
