"""Metrics computation engine for PromptProbe benchmarks.

Strictly separates probabilistic detection metrics (precision, recall, F1, FPR)
from deterministic action enforcement metrics (authorization correctness, containment).
"""

from promptprobe.models import (
    CaseEvaluationResult,
    ConfusionMatrix,
    EnforcementMetrics,
    EvaluationCase,
)


def compute_confusion_matrix(
    evaluations: list[tuple[EvaluationCase, CaseEvaluationResult]],
) -> ConfusionMatrix:
    """Compute confusion matrix and classification metrics for content detection.

    Scoring Rule:
    A case is evaluated as an individual binary classification instance (Positive = Finding
    emitted, Negative = Clean). Multi-finding cases are counted once per test case.
    """
    # Filter to cases that evaluate detector behavior
    detector_cases = [
        (c, r)
        for c, r in evaluations
        if c.tool_name is None  # Pure content detection cases
    ]

    tp = 0
    fp = 0
    tn = 0
    fn = 0

    for case, result in detector_cases:
        expected = case.expected_finding
        actual = result.actual_finding

        if expected and actual:
            tp += 1
        elif not expected and actual:
            fp += 1
        elif not expected and not actual:
            tn += 1
        else:  # expected and not actual
            fn += 1

    total = tp + fp + tn + fn

    # Calculate metrics with explicit handling of zero denominators
    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None

    if precision is not None and recall is not None and (precision + recall) > 0:
        f1_score = round((2 * precision * recall) / (precision + recall), 4)
    else:
        f1_score = None

    accuracy = round((tp + tn) / total, 4) if total > 0 else 0.0
    fpr = round(fp / (fp + tn), 4) if (fp + tn) > 0 else None

    notes_list: list[str] = []
    if precision is None:
        notes_list.append("Precision undefined: zero positive predictions (TP+FP=0).")
    if recall is None:
        notes_list.append("Recall undefined: zero actual positive samples (TP+FN=0).")
    if fpr is None:
        notes_list.append("FPR undefined: zero actual negative samples (FP+TN=0).")

    return ConfusionMatrix(
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        total_samples=total,
        precision=round(precision, 4) if precision is not None else None,
        recall=round(recall, 4) if recall is not None else None,
        f1_score=f1_score,
        accuracy=accuracy,
        false_positive_rate=fpr,
        notes=" ".join(notes_list),
    )


def compute_enforcement_metrics(
    evaluations: list[tuple[EvaluationCase, CaseEvaluationResult]],
) -> EnforcementMetrics:
    """Compute action-level policy enforcement and authorization metrics."""
    action_cases = [
        (c, r)
        for c, r in evaluations
        if c.tool_name is not None  # Tool action authorization cases
    ]

    total = len(action_cases)
    if total == 0:
        return EnforcementMetrics(
            total_action_cases=0,
            notes="No action authorization cases present in evaluation run.",
        )

    unauthorized_exec = 0
    correctly_denied = 0
    correctly_permitted = 0
    correctly_held_pending = 0
    prevented_invalid_or_unknown = 0
    correct_total = 0

    for case, result in action_cases:
        expected_status = case.expected_status
        actual_status = result.actual_status

        # Safety Violation: Action expected to be denied/pending but executed!
        if expected_status != "executed" and actual_status == "executed":
            unauthorized_exec += 1

        if expected_status == "executed" and actual_status == "executed":
            correctly_permitted += 1
            correct_total += 1
        elif expected_status == "denied" and actual_status == "denied":
            correctly_denied += 1
            correct_total += 1
            if case.expected_reason_code in ("DENY_UNKNOWN_TOOL", "DENY_INVALID_ARGUMENTS"):
                prevented_invalid_or_unknown += 1
        elif expected_status == "pending_approval" and actual_status == "pending_approval":
            correctly_held_pending += 1
            correct_total += 1

    accuracy = round(correct_total / total, 4) if total > 0 else None

    return EnforcementMetrics(
        total_action_cases=total,
        unauthorized_executions=unauthorized_exec,
        correctly_denied=correctly_denied,
        correctly_permitted=correctly_permitted,
        correctly_held_for_approval=correctly_held_pending,
        invalid_or_unknown_prevented=prevented_invalid_or_unknown,
        enforcement_accuracy=accuracy,
        notes="Unauthorized executions must be 0 for a passing security evaluation.",
    )
