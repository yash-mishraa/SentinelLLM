"""Executable module entrypoint for SentinelLLM."""

import sys

from sentinelllm.demo import run_demo

if __name__ == "__main__":
    sys.exit(run_demo())
