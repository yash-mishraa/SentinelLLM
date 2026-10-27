"""Tests for post-deployment smoke test runner."""

from unittest.mock import patch

import pytest

from scripts.smoke_test import SmokeTestError, run_smoke_suite


def test_smoke_suite_success_flow() -> None:
    """Verify that run_smoke_suite executes all checks and passes when endpoints return 200."""

    def mock_make_request(
        url: str, method: str = "GET", headers: dict[str, str] | None = None, **kwargs: object
    ) -> tuple[int, dict[str, object]]:
        if "health" in url:
            return 200, {"status": "ok", "version": "0.1.0"}
        if "ready" in url:
            return 200, {"status": "ready", "database_connected": True}
        if url.endswith("/api/v1/approvals") and method == "GET":
            if headers and headers.get("X-API-Key") == "sentinel-guest-key-secret":
                return 403, {"detail": "Guest lacks permission"}
            return 401, {"detail": "Missing API key"}
        if "benchmark/run" in url:
            return 403, {"detail": "Forbidden"}
        if "inspect" in url:
            return 200, {"decision": "ALLOW", "findings": []}
        if "authorize" in url:
            return 200, {"decision": "ALLOW"}
        if "execute" in url:
            return 200, {"status": "DENIED", "reason_code": "DENY_TEST"}
        return 200, {"status": "ok"}

    with patch("scripts.smoke_test.make_request", side_effect=mock_make_request):
        # Should complete without error
        run_smoke_suite(api_url="http://test-sentinel.local", staging=False)


def test_smoke_suite_fails_on_unhealthy_liveness() -> None:
    """Verify that run_smoke_suite raises SmokeTestError if liveness probe fails."""
    with (
        patch("scripts.smoke_test.make_request", return_value=(500, {"status": "error"})),
        pytest.raises(SmokeTestError, match="Liveness probe failed"),
    ):
        run_smoke_suite(api_url="http://test-sentinel.local")


def test_smoke_suite_staging_mutation_flow() -> None:
    """Verify staging flow creates and rejects approval."""

    def mock_make_request(
        url: str, method: str = "GET", headers: dict[str, str] | None = None, **kwargs: object
    ) -> tuple[int, dict[str, object]]:
        if "health" in url:
            return 200, {"status": "ok"}
        if "ready" in url:
            return 200, {"status": "ready", "database_connected": True}
        if url.endswith("/api/v1/approvals") and method == "GET":
            if headers and headers.get("X-API-Key") == "sentinel-guest-key-secret":
                return 403, {"detail": "Guest lacks permission"}
            return 401, {"detail": "Missing API key"}
        if "benchmark/run" in url:
            return 403, {"detail": "Forbidden"}
        if "inspect" in url:
            return 200, {"decision": "ALLOW", "findings": []}
        if "authorize" in url:
            return 200, {"decision": "ALLOW"}
        if "execute" in url:
            return 200, {"status": "DENIED", "reason_code": "DENY_TEST"}
        if url.endswith("/api/v1/approvals") and method == "POST":
            return 201, {"approval_id": "app_smoke_99"}
        if "/reject" in url:
            return 200, {"status": "REJECTED"}
        return 200, {}

    with patch("scripts.smoke_test.make_request", side_effect=mock_make_request):
        run_smoke_suite(api_url="http://test-sentinel.local", staging=True)


def test_smoke_cli_main_argument_aliases() -> None:
    """Verify CLI flags (-u, --url, -k, --api-key) are parsed and forwarded."""
    import sys

    from scripts.smoke_test import main

    test_args = [
        "smoke_test.py",
        "--url",
        "https://api.custom.local",
        "--api-key",
        "custom-admin-key",
        "--guest-key",
        "custom-guest-key",
        "--staging",
    ]
    with (
        patch.object(sys, "argv", test_args),
        patch("scripts.smoke_test.run_smoke_suite") as mock_suite,
    ):
        main()
        mock_suite.assert_called_once_with(
            api_url="https://api.custom.local",
            admin_key="custom-admin-key",
            guest_key="custom-guest-key",
            staging=True,
        )
