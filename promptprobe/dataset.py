"""Dataset loader and validator for PromptProbe benchmarks."""

import json
from pathlib import Path

from promptprobe.models import DatasetContainer


def get_default_dataset_path() -> Path:
    """Return the filesystem path to the bundled starter adversarial dataset."""
    root = Path(__file__).resolve().parent.parent
    return root / "benchmarks" / "datasets" / "starter_adversarial_v1.json"


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
