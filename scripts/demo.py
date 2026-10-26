#!/usr/bin/env python3
"""SentinelLLM portfolio demonstration entrypoint script."""

import sys
from pathlib import Path

# Add src to sys.path for direct script execution without prior installation
src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sentinelllm.demo import run_demo

if __name__ == "__main__":
    sys.exit(run_demo())
