"""Automated validation suite verifying deployment workflow safety invariants."""

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


def _load_deploy_workflow() -> dict[str, Any]:
    workflow_path = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "deploy.yml"
    assert workflow_path.is_file(), f"deploy.yml not found at {workflow_path}"
    with open(workflow_path, encoding="utf-8") as f:
        data: Any = yaml.safe_load(f)
    assert isinstance(data, dict)
    return data


def test_deploy_workflow_fail_closed_inputs() -> None:
    """Verify that workflow_dispatch requires explicit target and confirmation."""
    data = _load_deploy_workflow()
    triggers = data.get("on")
    assert triggers is not None
    dispatch = triggers["workflow_dispatch"]
    inputs = dispatch["inputs"]

    assert "target_environment" in inputs
    assert inputs["target_environment"]["default"] == "staging"
    assert inputs["target_environment"]["options"] == ["staging", "production"]

    assert "confirm_production" in inputs
    assert inputs["confirm_production"]["default"] == ""


def test_deploy_workflow_environment_separation() -> None:
    """Verify staging and production jobs are strictly separated."""
    data = _load_deploy_workflow()
    jobs = data["jobs"]

    assert "build-and-push-image" in jobs
    assert "validate-target" in jobs
    assert "deploy-staging" in jobs
    assert "deploy-production" in jobs

    staging_job = jobs["deploy-staging"]
    assert staging_job["environment"]["name"] == "staging"
    assert "is_staging" in staging_job["if"]

    prod_job = jobs["deploy-production"]
    assert prod_job["environment"]["name"] == "production"
    assert "is_production" in prod_job["if"]


def test_deploy_workflow_no_insecure_defaults() -> None:
    """Verify that no job or concurrency setting falls back to 'production' implicitly."""
    data = _load_deploy_workflow()

    concurrency = str(data.get("concurrency", {}))
    assert "|| 'production'" not in concurrency
    assert '|| "production"' not in concurrency

    # Ensure neither staging nor production job uses fallback environment names
    for job_name in ["deploy-staging", "deploy-production"]:
        env_def = data["jobs"][job_name]["environment"]
        assert isinstance(env_def, dict)
        assert env_def["name"] in ("staging", "production")
