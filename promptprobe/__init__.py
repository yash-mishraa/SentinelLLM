"""PromptProbe: Automated adversarial evaluation and benchmarking suite for LLM defenses.

Companion framework to SentinelLLM for executing security benchmarks, measuring
attack success rates (ASR), and performing reproducible ablation studies.
"""

from typing import Final

from promptprobe.baselines import (
    BASELINE_HEURISTIC,
    BASELINE_NO_DETECTION,
    create_heuristic_defense,
    create_no_detection_baseline,
)
from promptprobe.dataset import (
    get_default_dataset_path,
    get_default_scenario_dataset_path,
    load_dataset,
    load_scenario_dataset,
)
from promptprobe.metrics import compute_confusion_matrix, compute_enforcement_metrics
from promptprobe.models import (
    BenchmarkReport,
    CaseEvaluationResult,
    ConfusionMatrix,
    DatasetContainer,
    EnforcementMetrics,
    EvaluationCase,
    EvaluationCategory,
)
from promptprobe.runner import BenchmarkRunner
from promptprobe.scenario_models import (
    ScenarioBenchmarkReport,
    ScenarioDatasetContainer,
    ScenarioMetrics,
    ScenarioResult,
    ScenarioStep,
    ScenarioStepResult,
    ScenarioStepType,
    SecurityScenario,
)
from promptprobe.scenario_runner import ScenarioRunner

__version__: Final[str] = "0.1.0.dev0"

__all__: Final[list[str]] = [
    "BASELINE_HEURISTIC",
    "BASELINE_NO_DETECTION",
    "BenchmarkReport",
    "BenchmarkRunner",
    "CaseEvaluationResult",
    "ConfusionMatrix",
    "DatasetContainer",
    "EnforcementMetrics",
    "EvaluationCase",
    "EvaluationCategory",
    "ScenarioBenchmarkReport",
    "ScenarioDatasetContainer",
    "ScenarioMetrics",
    "ScenarioResult",
    "ScenarioRunner",
    "ScenarioStep",
    "ScenarioStepResult",
    "ScenarioStepType",
    "SecurityScenario",
    "__version__",
    "compute_confusion_matrix",
    "compute_enforcement_metrics",
    "create_heuristic_defense",
    "create_no_detection_baseline",
    "get_default_dataset_path",
    "get_default_scenario_dataset_path",
    "load_dataset",
    "load_scenario_dataset",
]
