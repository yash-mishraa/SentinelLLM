"""Dataset loader and validator for PromptProbe benchmarks."""

import json
from pathlib import Path

from promptprobe.models import DatasetContainer
from promptprobe.scenario_models import ScenarioDatasetContainer


def get_default_dataset_path() -> Path:
    """Return the filesystem path to the bundled starter adversarial dataset."""
    root = Path(__file__).resolve().parent.parent
    return root / "benchmarks" / "datasets" / "starter_adversarial_v1.json"


def get_default_scenario_dataset_path() -> Path:
    """Return the filesystem path to the bundled starter multi-step scenario dataset."""
    root = Path(__file__).resolve().parent.parent
    return root / "benchmarks" / "datasets" / "starter_scenarios_v1.json"


def load_dataset(dataset_path: str | Path | None = None) -> DatasetContainer:
    """Load and schema-validate a PromptProbe benchmark dataset.

    Args:
        dataset_path: Optional path to JSON dataset file. Defaults to bundled starter dataset.

    Returns:
        Validated DatasetContainer.

    Raises:
        FileNotFoundError: If the specified dataset file does not exist.
        ValueError: If JSON is invalid or fails schema validation.
    """
    path = Path(dataset_path) if dataset_path is not None else get_default_dataset_path()
    if not path.is_file():
        raise FileNotFoundError(f"Benchmark dataset file not found: {path}")

    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as err:
            raise ValueError(f"Malformed JSON in dataset file '{path}': {err}") from err

    return DatasetContainer.model_validate(data)


def load_scenario_dataset(dataset_path: str | Path | None = None) -> ScenarioDatasetContainer:
    """Load and schema-validate a PromptProbe multi-step scenario dataset.

    Args:
        dataset_path: Optional path to scenario JSON file. Defaults to starter scenarios.

    Returns:
        Validated ScenarioDatasetContainer.

    Raises:
        FileNotFoundError: If the specified dataset file does not exist.
        ValueError: If JSON is invalid or fails schema validation.
    """
    path = Path(dataset_path) if dataset_path is not None else get_default_scenario_dataset_path()
    if not path.is_file():
        raise FileNotFoundError(f"Scenario dataset file not found: {path}")

    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as err:
            raise ValueError(f"Malformed JSON in scenario dataset file '{path}': {err}") from err

    return ScenarioDatasetContainer.model_validate(data)
