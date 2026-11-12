SHELL := bash
UV ?= uv

.PHONY: help install run test lint lint-fix check clean

help:
	@echo "Available commands:"
	@echo "  install   - install development dependencies"
	@echo "  run       - run the FastAPI proxy server with auto-reload"
	@echo "  test      - run unit and integration tests with pytest"
	@echo "  lint      - run ruff linter and formatting checks"
	@echo "  lint-fix  - automatically fix lint and formatting violations"
	@echo "  check     - run full validation (lint + test)"
	@echo "  clean     - clean temporary and build files"

install:
	$(UV) sync

run:
	$(UV) run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	$(UV) run pytest -v

lint:
	$(UV) run ruff check . && $(UV) run ruff format --check .

lint-fix:
	$(UV) run ruff check --fix . && $(UV) run ruff format .

check: lint test

clean:
	rm -rf .venv .pytest_cache .ruff_cache htmlcov .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +
