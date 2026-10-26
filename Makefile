.PHONY: help install lint format typecheck test check build clean benchmark scenarios demo

PYTHON ?= $(shell if [ -f .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
PIP ?= $(shell if [ -f .venv/bin/pip ]; then echo .venv/bin/pip; else echo pip; fi)

help:
	@echo "SentinelLLM Development Automation"
	@echo ""
	@echo "Available targets:"
	@echo "  install    Install package in editable mode with development dependencies"
	@echo "  lint       Run Ruff linting checks"
	@echo "  format     Format code using Ruff"
	@echo "  typecheck  Run Mypy static type analysis"
	@echo "  test       Run unit, integration, and security tests with coverage"
	@echo "  benchmark  Run PromptProbe adversarial evaluation benchmark suite"
	@echo "  scenarios  Run PromptProbe multi-step adversarial scenario evaluations"
	@echo "  check      Run full quality gate pipeline (lint, format check, typecheck, test, build)"
	@echo "  build      Build source distribution and wheel packages"
	@echo "  clean      Remove temporary build artifacts and cache files"

install:
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	@if command -v pre-commit >/dev/null 2>&1; then pre-commit install; fi

lint:
	$(PYTHON) -m ruff check src promptprobe tests

format:
	$(PYTHON) -m ruff format src promptprobe tests
	$(PYTHON) -m ruff check --fix src promptprobe tests

typecheck:
	$(PYTHON) -m mypy src promptprobe tests

test:
	$(PYTHON) -m pytest --cov=sentinelllm --cov=promptprobe --cov-report=term-missing tests

benchmark:
	$(PYTHON) -m promptprobe run --include-scenarios

scenarios:
	$(PYTHON) -m promptprobe scenarios

demo:
	$(PYTHON) -m sentinelllm.demo


build:
	$(PYTHON) -m build

check: lint typecheck test build
	$(PYTHON) -m ruff format --check src promptprobe tests
	@echo ""
	@echo "All quality gate checks passed successfully."

clean:
	rm -rf build/ dist/ *.egg-info src/*.egg-info
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/ htmlcov/ .coverage*
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
