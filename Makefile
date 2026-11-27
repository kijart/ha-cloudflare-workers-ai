.PHONY: install lint format test check

install:
	uv sync

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy custom_components scripts

format:
	uv run ruff check --fix .
	uv run ruff format .

test:
	uv run pytest --cov=custom_components.cloudflare_workers_ai --cov-report=term-missing --cov-fail-under=95

check: lint test
