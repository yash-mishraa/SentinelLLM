"""CLI entrypoint for running the SentinelLLM REST Gateway."""

import sys

import uvicorn

from sentinelllm.api.config import ApiConfig


def run_api() -> int:
    """Launch the Uvicorn ASGI server with configured host and port."""
    config = ApiConfig.from_env()
    print(f"Starting SentinelLLM Gateway on http://{config.host}:{config.port}")
    uvicorn.run(
        "sentinelllm.api.app:app",
        host=config.host,
        port=config.port,
        log_level="info",
        reload=False,
    )
    return 0


if __name__ == "__main__":
    sys.exit(run_api())
