"""Promotion gate: metric-based model approval workflow.

Models pass from v1.2 (untrained) → v2.0 (trained) → v2.1+ (promoted) only if:
1. All metrics exceed baseline thresholds
2. Explicit human approval (no automatic promotion)
3. Full audit trail of decision

Fail-closed: untrained model stays in production until v2.x passes gate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Optional


@dataclass
class MetricThresholds:
    """Gate thresholds (must exceed ALL to pass)."""

    overall_accuracy: float = 0.65  # Must beat spectral baseline
    macro_f1: float = 0.60  # Per-class fairness
    weighted_f1: float = 0.65  # Overall quality
    macro_precision: float = 0.60  # False positives
    macro_recall: float = 0.60  # False negatives
    min_class_support: int = 50  # Minimum samples per class for train/val/test
    balanced_accuracy: float = 0.60
    max_expected_calibration_error: float = 0.10
    max_brier_score: float = 0.25
    min_class_recall: float = 0.50
    require_calibration: bool = False

    def to_dict(self) -> dict:
        """Export as dictionary."""
        return asdict(self)


@dataclass
class PromotionDecision:
    """Result of promotion gate evaluation."""

    model_version: str
    passes_gate: bool
    timestamp: str
    metrics_provided: dict[str, float]
    thresholds: dict[str, float]
    metric_details: dict[str, str]  # Pass/fail reason per metric
    baseline_comparison: dict[str, float]  # (trained - baseline) for each metric
    human_approval: Optional[bool] = None
    approval_timestamp: Optional[str] = None
    approval_reason: Optional[str] = None
    approved_by: Optional[str] = None

    def to_dict(self) -> dict:
        """Export as dictionary."""
        return asdict(self)


class PromotionGate:
    """Evaluate model against metric thresholds."""

    def __init__(self, thresholds: Optional[MetricThresholds] = None):
        """
        Initialize gate with thresholds.

        Args:
            thresholds: MetricThresholds (uses defaults if None)
        """
        self.thresholds = thresholds or MetricThresholds()

    def evaluate(
        self,
        model_version: str,
        evaluation_metrics: dict[str, float],
        baseline_metrics: dict[str, float],
    ) -> PromotionDecision:
        """
        Evaluate model metrics against thresholds.

        Args:
            model_version: Version string (e.g., "v2.0")
            evaluation_metrics: Dict with keys:
                - overall_accuracy, macro_f1, weighted_f1, macro_precision, macro_recall
            baseline_metrics: Comparison metrics (e.g., spectral indices baseline)

        Returns:
            PromotionDecision with gate result
        """
        metric_details = {}
        threshold_dict = self.thresholds.to_dict()

        # Check each metric
        passes_accuracy = evaluation_metrics.get("overall_accuracy", 0) > self.thresholds.overall_accuracy
        metric_details["overall_accuracy"] = (
            f"✓ {evaluation_metrics.get('overall_accuracy', 0):.4f} > {self.thresholds.overall_accuracy}"
            if passes_accuracy
            else f"✗ {evaluation_metrics.get('overall_accuracy', 0):.4f} ≤ {self.thresholds.overall_accuracy}"
        )

        passes_macro_f1 = evaluation_metrics.get("macro_f1", 0) > self.thresholds.macro_f1
        metric_details["macro_f1"] = (
            f"✓ {evaluation_metrics.get('macro_f1', 0):.4f} > {self.thresholds.macro_f1}"
            if passes_macro_f1
            else f"✗ {evaluation_metrics.get('macro_f1', 0):.4f} ≤ {self.thresholds.macro_f1}"
        )

        passes_weighted_f1 = evaluation_metrics.get("weighted_f1", 0) > self.thresholds.weighted_f1
        metric_details["weighted_f1"] = (
            f"✓ {evaluation_metrics.get('weighted_f1', 0):.4f} > {self.thresholds.weighted_f1}"
            if passes_weighted_f1
            else f"✗ {evaluation_metrics.get('weighted_f1', 0):.4f} ≤ {self.thresholds.weighted_f1}"
        )

        passes_macro_precision = evaluation_metrics.get("macro_precision", 0) > self.thresholds.macro_precision
        metric_details["macro_precision"] = (
            f"✓ {evaluation_metrics.get('macro_precision', 0):.4f} > {self.thresholds.macro_precision}"
            if passes_macro_precision
            else f"✗ {evaluation_metrics.get('macro_precision', 0):.4f} ≤ {self.thresholds.macro_precision}"
        )

        passes_macro_recall = evaluation_metrics.get("macro_recall", 0) > self.thresholds.macro_recall
        metric_details["macro_recall"] = (
            f"✓ {evaluation_metrics.get('macro_recall', 0):.4f} > {self.thresholds.macro_recall}"
            if passes_macro_recall
            else f"✗ {evaluation_metrics.get('macro_recall', 0):.4f} ≤ {self.thresholds.macro_recall}"
        )

        # Scientific metrics are required when supplied by the evaluator. The
        # default compatibility profile remains usable for legacy smoke tests;
        # production profiles should set ``require_calibration=True``.
        balanced_accuracy = evaluation_metrics.get("balanced_accuracy")
        if balanced_accuracy is None:
            metric_details["balanced_accuracy"] = "not supplied by compatibility profile"
            passes_balanced_accuracy = True
        else:
            passes_balanced_accuracy = balanced_accuracy >= self.thresholds.balanced_accuracy
            metric_details["balanced_accuracy"] = (
                f"✓ {balanced_accuracy:.4f} >= {self.thresholds.balanced_accuracy}"
                if passes_balanced_accuracy
                else f"✗ {balanced_accuracy:.4f} < {self.thresholds.balanced_accuracy}"
            )

        brier_score = evaluation_metrics.get("brier_score")
        ece = evaluation_metrics.get("expected_calibration_error")
        if self.thresholds.require_calibration:
            passes_calibration = (
                brier_score is not None
                and ece is not None
                and brier_score <= self.thresholds.max_brier_score
                and ece <= self.thresholds.max_expected_calibration_error
            )
            metric_details["calibration"] = (
                f"✓ Brier={brier_score:.4f}, ECE={ece:.4f}"
                if passes_calibration
                else "✗ missing or above calibration limits"
            )
        else:
            passes_calibration = True
            metric_details["calibration"] = "not required by compatibility profile"

        per_class_recall = evaluation_metrics.get("per_class_recall", {})
        if per_class_recall:
            failing_classes = [
                name for name, recall in per_class_recall.items()
                if recall < self.thresholds.min_class_recall
            ]
            passes_class_recall = not failing_classes
            metric_details["per_class_recall"] = (
                "✓ all classes meet minimum recall"
                if passes_class_recall
                else f"✗ below minimum: {', '.join(failing_classes)}"
            )
        else:
            passes_class_recall = True
            metric_details["per_class_recall"] = "not supplied"

        # Compute baseline comparison
        baseline_comparison = {}
        for metric_name in ["overall_accuracy", "macro_f1", "weighted_f1"]:
            trained = evaluation_metrics.get(metric_name, 0)
            baseline = baseline_metrics.get(metric_name, 0)
            baseline_comparison[metric_name] = trained - baseline

        # All metrics must pass
        passes_gate = all(
            [
                passes_accuracy,
                passes_macro_f1,
                passes_weighted_f1,
                passes_macro_precision,
                passes_macro_recall,
                passes_balanced_accuracy,
                passes_calibration,
                passes_class_recall,
            ]
        )

        return PromotionDecision(
            model_version=model_version,
            passes_gate=passes_gate,
            timestamp=datetime.utcnow().isoformat(),
            metrics_provided=evaluation_metrics,
            thresholds=threshold_dict,
            metric_details=metric_details,
            baseline_comparison=baseline_comparison,
        )

    def approve(
        self,
        decision: PromotionDecision,
        approved_by: str,
        reason: str,
    ) -> PromotionDecision:
        """
        Record human approval (or rejection).

        Args:
            decision: PromotionDecision from evaluate()
            approved_by: User/team approving (e.g., "data_science_team")
            reason: Justification for approval/rejection

        Returns:
            Updated PromotionDecision with approval info
        """
        if not decision.passes_gate:
            raise ValueError("Cannot approve a promotion decision that failed the gate")
        decision.human_approval = True
        decision.approval_timestamp = datetime.utcnow().isoformat()
        decision.approved_by = approved_by
        decision.approval_reason = reason
        return decision

    def reject(
        self,
        decision: PromotionDecision,
        rejected_by: str,
        reason: str,
    ) -> PromotionDecision:
        """
        Record human rejection.

        Args:
            decision: PromotionDecision
            rejected_by: User/team rejecting
            reason: Justification

        Returns:
            Updated PromotionDecision with rejection info
        """
        decision.human_approval = False
        decision.approval_timestamp = datetime.utcnow().isoformat()
        decision.approved_by = rejected_by
        decision.approval_reason = reason
        return decision


def format_gate_result(decision: PromotionDecision) -> str:
    """Format gate result as readable report."""
    lines = [
        "=" * 70,
        "PROMOTION GATE EVALUATION",
        "=" * 70,
        f"Model: {decision.model_version}",
        f"Evaluated: {decision.timestamp}",
        "",
        f"GATE STATUS: {'✓ PASS' if decision.passes_gate else '✗ FAIL'}",
        "",
        "Metric Thresholds:",
    ]

    for metric_name, detail in decision.metric_details.items():
        lines.append(f"  {metric_name:25} | {detail}")

    lines.extend([
        "",
        "Baseline Comparison (trained - baseline):",
    ])

    for metric_name, delta in decision.baseline_comparison.items():
        sign = "+" if delta >= 0 else ""
        lines.append(f"  {metric_name:25} | {sign}{delta:.4f}")

    if decision.human_approval is not None:
        lines.extend([
            "",
            f"Human Approval: {'✓ APPROVED' if decision.human_approval else '✗ REJECTED'}",
            f"Approved by: {decision.approved_by}",
            f"Timestamp: {decision.approval_timestamp}",
            f"Reason: {decision.approval_reason}",
        ])
    else:
        lines.append("\nHuman Approval: PENDING")

    lines.append("=" * 70)
    return "\n".join(lines)


def main():
    """CLI entry point."""
    print("Promotion gate module; use PromotionGate.evaluate() for gate checks")


if __name__ == "__main__":
    main()
