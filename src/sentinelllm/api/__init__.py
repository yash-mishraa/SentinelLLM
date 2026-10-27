"""FastAPI REST Gateway package for SentinelLLM."""

from sentinelllm.api.app import app, create_app
from sentinelllm.api.config import ApiConfig

__all__ = ["ApiConfig", "app", "create_app"]
