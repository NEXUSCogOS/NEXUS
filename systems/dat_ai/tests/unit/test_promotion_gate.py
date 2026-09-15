"""Tests for promotion gate."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestMetricThresholds:
    """Test metric threshold configuration."""

    def test_default_thresholds(self):
        """Should have sensible defaults."""
        from app.ml.promotion_gate import MetricThresholds

        thresholds = MetricThresholds()
        assert thresholds.overall_accuracy == 0.65
        assert thresholds.macro_f1 == 0.60
        assert thresholds.weighted_f1 == 0.65

    def test_custom_thresholds(self):
        """Should accept custom thresholds."""
        from app.ml.promotion_gate import MetricThresholds

        thresholds = MetricThresholds(
            overall_accuracy=0.75,
            macro_f1=0.70,
        )
        assert thresholds.overall_accuracy == 0.75
        assert thresholds.macro_f1 == 0.70

    def test_thresholds_to_dict(self):
        """Should serialize to dict."""
        from app.ml.promotion_gate import MetricThresholds

        thresholds = MetricThresholds()
        d = thresholds.to_dict()
        assert d["overall_accuracy"] == 0.65


class TestPromotionDecision:
    """Test promotion decision."""

    def test_decision_creation(self):
        """Decision should record all info."""
        from app.ml.promotion_gate import PromotionDecision

        decision = PromotionDecision(
            model_version="v2.0",
            passes_gate=True,
            timestamp="2026-08-14T12:00:00",
            metrics_provided={"overall_accuracy": 0.75},
            thresholds={"overall_accuracy": 0.65},
            metric_details={"overall_accuracy": "✓ 0.75 > 0.65"},
            baseline_comparison={"overall_accuracy": 0.10},
        )

        assert decision.model_version == "v2.0"
        assert decision.passes_gate is True

    def test_decision_to_dict(self):
        """Decision should serialize to dict."""
        from app.ml.promotion_gate import PromotionDecision

        decision = PromotionDecision(
            model_version="v2.0",
            passes_gate=True,
            timestamp="2026-08-14T12:00:00",
            metrics_provided={},
            thresholds={},
            metric_details={},
            baseline_comparison={},
        )

        d = decision.to_dict()
        assert d["model_version"] == "v2.0"
        assert d["passes_gate"] is True


class TestPromotionGate:
    """Test promotion gate evaluation."""

    def test_gate_passes_all_metrics(self):
        """Gate should pass when all metrics exceed thresholds."""
        from app.ml.promotion_gate import PromotionGate, MetricThresholds

        gate = PromotionGate(
            thresholds=MetricThresholds(
                overall_accuracy=0.60,
                macro_f1=0.55,
                weighted_f1=0.60,
                macro_precision=0.55,
                macro_recall=0.55,
            )
        )

        metrics = {
            "overall_accuracy": 0.75,
            "macro_f1": 0.70,
            "weighted_f1": 0.72,
            "macro_precision": 0.70,
            "macro_recall": 0.68,
        }
        baseline_metrics = {
            "overall_accuracy": 0.50,
            "macro_f1": 0.40,
            "weighted_f1": 0.45,
        }

        decision = gate.evaluate("v2.0", metrics, baseline_metrics)
        assert decision.passes_gate is True

    def test_gate_fails_one_metric(self):
        """Gate should fail if any metric is below threshold."""
        from app.ml.promotion_gate import PromotionGate, MetricThresholds

        gate = PromotionGate(
            thresholds=MetricThresholds(
                overall_accuracy=0.70,
                macro_f1=0.70,
                weighted_f1=0.70,
                macro_precision=0.70,
                macro_recall=0.70,
            )
        )

        metrics = {
            "overall_accuracy": 0.75,
            "macro_f1": 0.65,  # Below threshold
            "weighted_f1": 0.72,
            "macro_precision": 0.70,
            "macro_recall": 0.68,
        }
        baseline_metrics = {}

        decision = gate.evaluate("v2.0", metrics, baseline_metrics)
        assert decision.passes_gate is False
        assert "✗" in decision.metric_details["macro_f1"]

    def test_gate_baseline_comparison(self):
        """Gate should compute delta from baseline."""
        from app.ml.promotion_gate import PromotionGate

        gate = PromotionGate()
        metrics = {"overall_accuracy": 0.80, "macro_f1": 0.75, "weighted_f1": 0.78}
        baseline = {"overall_accuracy": 0.50, "macro_f1": 0.40, "weighted_f1": 0.45}

        decision = gate.evaluate("v2.0", metrics, baseline)

        assert decision.baseline_comparison["overall_accuracy"] == pytest.approx(0.30)
        assert decision.baseline_comparison["macro_f1"] == pytest.approx(0.35)

    def test_gate_approve(self):
        """Gate should record human approval."""
        from app.ml.promotion_gate import PromotionGate, PromotionDecision

        gate = PromotionGate()
        decision = PromotionDecision(
            model_version="v2.0",
            passes_gate=True,
            timestamp="2026-08-14T12:00:00",
            metrics_provided={},
            thresholds={},
            metric_details={},
            baseline_comparison={},
        )

        approved = gate.approve(decision, "data_science_team", "Metrics exceed thresholds + domain validation")

        assert approved.human_approval is True
        assert approved.approved_by == "data_science_team"
        assert "domain validation" in approved.approval_reason

    def test_gate_cannot_approve_failed_decision(self):
        """A failed automatic gate must remain non-approvable."""
        from app.ml.promotion_gate import PromotionGate, PromotionDecision

        decision = PromotionDecision(
            model_version="v2.0",
            passes_gate=False,
            timestamp="2026-08-14T12:00:00",
            metrics_provided={},
            thresholds={},
            metric_details={},
            baseline_comparison={},
        )
        with pytest.raises(ValueError, match="failed the gate"):
            PromotionGate().approve(decision, "review_board", "override")

    def test_scientific_profile_requires_calibration(self):
        """The scientific profile fails when calibration evidence is absent."""
        from app.ml.promotion_gate import MetricThresholds, PromotionGate

        gate = PromotionGate(MetricThresholds(require_calibration=True))
        metrics = {
            "overall_accuracy": 0.80,
            "macro_f1": 0.75,
            "weighted_f1": 0.78,
            "macro_precision": 0.76,
            "macro_recall": 0.74,
            "balanced_accuracy": 0.74,
        }
        decision = gate.evaluate("v2.0", metrics, {})
        assert decision.passes_gate is False
        assert "calibration" in decision.metric_details

    def test_gate_reject(self):
        """Gate should record human rejection."""
        from app.ml.promotion_gate import PromotionGate, PromotionDecision

        gate = PromotionGate()
        decision = PromotionDecision(
            model_version="v2.0",
            passes_gate=False,
            timestamp="2026-08-14T12:00:00",
            metrics_provided={},
            thresholds={},
            metric_details={},
            baseline_comparison={},
        )

        rejected = gate.reject(decision, "review_board", "Forest class F1 too low (0.45)")

        assert rejected.human_approval is False
        assert rejected.approved_by == "review_board"
        assert "Forest class" in rejected.approval_reason


class TestPromotionGateFormatting:
    """Test gate result formatting."""

    def test_format_gate_result(self):
        """format_gate_result should produce readable output."""
        from app.ml.promotion_gate import PromotionGate, format_gate_result

        gate = PromotionGate()
        metrics = {
            "overall_accuracy": 0.80,
            "macro_f1": 0.75,
            "weighted_f1": 0.78,
            "macro_precision": 0.76,
            "macro_recall": 0.74,
        }
        baseline = {
            "overall_accuracy": 0.50,
            "macro_f1": 0.40,
            "weighted_f1": 0.45,
        }

        decision = gate.evaluate("v2.0", metrics, baseline)
        formatted = format_gate_result(decision)

        assert "PROMOTION GATE EVALUATION" in formatted
        assert "v2.0" in formatted
        assert "GATE STATUS: ✓ PASS" in formatted
        assert "Baseline Comparison" in formatted


def test_import():
    """Module should import without errors."""
    from app.ml import promotion_gate
    assert promotion_gate.PromotionGate is not None
    assert promotion_gate.format_gate_result is not None
