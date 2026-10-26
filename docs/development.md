# SentinelLLM Development Guide

This document provides developer guidelines, local environment setup instructions, and code quality standards for contributors to SentinelLLM.

---

## 1. Prerequisites and Tooling

- **Python:** Python 3.12 or newer.
- **Git:** Git 2.30+ installed and configured.
- **Package & Environment Manager:** `uv` (recommended) or standard `venv` + `pip`.
- **Make:** GNU Make for running automated standard workflow commands.

---

## 2. Local Environment Setup

### Option A: Using `uv` (Recommended)

```bash
# Clone the repository
git clone https://github.com/yash-mishraa/SentinelLLM.git
cd SentinelLLM

# Create virtual environment with Python 3.12
uv venv .venv --python 3.12

# Activate virtual environment
source .venv/bin/activate

# Install SentinelLLM in editable mode with development dependencies
uv pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Option B: Using standard Python `venv` and `pip`

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pre-commit install
```

---

## 3. Development Workflow & Quality Gates

SentinelLLM enforces strict quality gates on all code submissions. All checks must pass before opening pull requests.

### Common `make` Commands

A standard `Makefile` is provided in the repository root:

```bash
# Install package and all dev dependencies
make install

# Run Ruff linter
make lint

# Automatically format code using Ruff
make format

# Run Mypy static type checker
make typecheck

# Run Pytest test suite with code coverage
make test

# Run the complete quality verification pipeline (lint + typecheck + test + build)
make check

# Build the distributable sdist and wheel packages
make build

# Clean temporary build and cache files
make clean
```

---

## 4. Engineering & Code Standards

### 4.1 Type Annotations
- All production code must be fully type-annotated (`mypy` runs in strict mode).
- Public APIs must avoid `Any` where specific types or generics can be expressed.
- The package ships with a `py.typed` marker (PEP 561 compliance).

### 4.2 Linting & Formatting
- Code is formatted using `ruff` with a maximum line length of 100 characters.
- Imports must be grouped and alphabetized (enforced by `ruff` isort integration).
- Unused imports, variables, and broad catch blocks are prohibited.

### 4.3 Testing Discipline
- Unit tests live under `tests/unit/`.
- Integration tests live under `tests/integration/`.
- Security tests and regression fixtures live under `tests/security/`.
- Test names should be descriptive: `test_<component>_<scenario>_<expected_result>()`.
- Minimum code coverage target is 80%.

### 4.4 Git Commit Conventions
Follow the Conventional Commits specification:
- `feat:` A new feature or capability.
- `fix:` A bug fix.
- `docs:` Documentation updates or additions.
- `chore:` Maintenance, dependency updates, CI/build configuration.
- `test:` Adding or updating tests.
- `refactor:` Code reorganization without behavioral alterations.

---

## 5. Security & Sensitive Data Handling

- **Never commit `.env` or secrets.** Keep `.env.example` as the source of truth for configuration keys.
- **Never embed real credentials or live API keys in tests or documentation.**
- Run tests and benchmarks exclusively against simulated services and mock LLM providers during local development.
