"""Foundation test suite verifying package imports, versioning, and typing markers."""

import re
from pathlib import Path

import promptprobe
import sentinelllm


def test_sentinelllm_version_format() -> None:
    """Verify SentinelLLM exposes a valid PEP 440 semantic version."""
    version = sentinelllm.__version__
    assert isinstance(version, str)
    assert len(version) > 0
    # Standard semver / dev version regex (e.g. 0.1.0 or 0.1.0.dev0)
    pattern = r"^\d+\.\d+\.\d+(\.dev\d+)?$"
    assert re.match(pattern, version) is not None, f"Unexpected version format: {version}"


def test_sentinelllm_all_exports() -> None:
    """Verify __all__ is properly exposed and exports match defined symbols."""
    assert hasattr(sentinelllm, "__all__")
    assert "__version__" in sentinelllm.__all__
    for symbol in sentinelllm.__all__:
        assert hasattr(sentinelllm, symbol)


def test_sentinelllm_py_typed_marker_present() -> None:
    """Verify that the PEP 561 py.typed marker is present in the package directory."""
    package_dir = Path(sentinelllm.__file__).resolve().parent
    py_typed_file = package_dir / "py.typed"
    assert py_typed_file.is_file(), f"Missing py.typed marker in {package_dir}"


def test_promptprobe_version_format() -> None:
    """Verify PromptProbe exposes a valid PEP 440 semantic version."""
    version = promptprobe.__version__
    assert isinstance(version, str)
    assert len(version) > 0
    pattern = r"^\d+\.\d+\.\d+(\.dev\d+)?$"
    assert re.match(pattern, version) is not None, f"Unexpected version format: {version}"


def test_promptprobe_all_exports() -> None:
    """Verify PromptProbe __all__ is properly exposed."""
    assert hasattr(promptprobe, "__all__")
    assert "__version__" in promptprobe.__all__
    for symbol in promptprobe.__all__:
        assert hasattr(promptprobe, symbol)
