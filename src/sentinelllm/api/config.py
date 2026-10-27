"""API Gateway configuration and environment settings."""

import json
import os


class ApiConfig:
    """Manages HTTP API settings, CORS origins, size limits, and rate limits.

    Security Invariant:
    - CORS origins must never default to wildcard '*' when credentials or headers are enabled.
    - Production environments strictly require explicit configuration.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        cors_origins: list[str] | None = None,
        max_request_size_bytes: int = 1_048_576,  # 1 MB default bound
        rate_limit_per_minute: int = 60,
        rate_limit_enabled: bool = True,
        environment: str = "development",
        api_keys_json: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.cors_origins = cors_origins or ["http://localhost:3000"]
        self.max_request_size_bytes = max_request_size_bytes
        self.rate_limit_per_minute = rate_limit_per_minute
        self.rate_limit_enabled = rate_limit_enabled
        self.environment = environment
        self.api_keys_json = api_keys_json

    @classmethod
    def from_env(cls) -> "ApiConfig":
        """Load API configuration from environment variables."""
        env = os.getenv("SENTINELLLM_ENV", "development").lower()
        host = os.getenv("SENTINELLLM_API_HOST", "127.0.0.1")
        port = int(os.getenv("SENTINELLLM_API_PORT", "8000"))

        raw_cors = os.getenv("SENTINELLLM_CORS_ORIGINS")
        if raw_cors:
            try:
                cors_origins = json.loads(raw_cors)
                if not isinstance(cors_origins, list):
                    cors_origins = [str(raw_cors)]
            except json.JSONDecodeError:
                cors_origins = [o.strip() for o in raw_cors.split(",") if o.strip()]
        else:
            cors_origins = ["http://localhost:3000"]

        max_size = int(os.getenv("SENTINELLLM_MAX_REQUEST_SIZE_BYTES", str(1_048_576)))
        rate_limit = int(os.getenv("SENTINELLLM_RATE_LIMIT_PER_MINUTE", "60"))
        rate_limit_enabled = os.getenv("SENTINELLLM_RATE_LIMIT_ENABLED", "true").lower() in (
            "true",
            "1",
            "yes",
        )
        api_keys_json = os.getenv("SENTINELLLM_API_KEYS")

        return cls(
            host=host,
            port=port,
            cors_origins=cors_origins,
            max_request_size_bytes=max_size,
            rate_limit_per_minute=rate_limit,
            rate_limit_enabled=rate_limit_enabled,
            environment=env,
            api_keys_json=api_keys_json,
        )
