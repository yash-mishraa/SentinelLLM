# Operational & Research Scripts

This directory contains standalone maintenance, data transformation, and utility scripts used across development and evaluation workflows.

## Guidelines

- Scripts should be idempotent, documented, and executable with standard Python or POSIX shell commands.
- Arguments should use standard CLI parsing (`argparse` or `click`) with sensible defaults and `--help` output.
- All Python scripts must conform to the project's formatting, linting, and type-checking standards defined in `pyproject.toml`.
