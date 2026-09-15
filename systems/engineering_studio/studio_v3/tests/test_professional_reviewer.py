"""Tests for professional_reviewer.py."""

from __future__ import annotations

import pytest

from systems.engineering_studio.studio_v3.quality.professional_reviewer import (
    ArchitectureScore,
    CodeQualityScore,
    PerformanceAudit,
    ProfessionalCodeReviewer,
    ReviewResult,
    SecurityAudit,
)


GOOD_CODE = '''
"""A small, well-documented module."""


class Calculator:
    """Performs basic arithmetic operations."""

    def add(self, a: int, b: int) -> int:
        """Return the sum of a and b."""
        return a + b

    def divide(self, a: int, b: int) -> float:
        """Return a divided by b.

        Raises:
            ValueError: if b is zero.
        """
        if b == 0:
            raise ValueError("division by zero")
        return a / b


def test_add() -> None:
    """Test Calculator.add."""
    assert Calculator().add(1, 2) == 3


def test_divide() -> None:
    """Test Calculator.divide."""
    assert Calculator().divide(6, 2) == 3.0
'''


BAD_CODE = '''
import os

def BadName(Password, apiKey="SYNTHETIC_AWS_KEY_FOR_TESTING"):
    if Password == "hunter2":
        os.system("rm -rf " + Password)
    result = ""
    for i in range(1000):
        for j in range(1000):
            result += str(i * j)
    return eval(Password)
'''


UNPARSEABLE_CODE = "def broken(:\n    pass"


@pytest.fixture
def reviewer() -> ProfessionalCodeReviewer:
    return ProfessionalCodeReviewer()


# --------------------------------------------------------------------
# Dataclass construction tests
# --------------------------------------------------------------------


class TestReviewResultCreation:
    def test_construct_review_result(self) -> None:
        quality = CodeQualityScore(
            overall_score=0.9,
            cyclomatic_complexity=2.0,
            max_cyclomatic_complexity=3,
            naming_convention_score=1.0,
            modularity_score=1.0,
            function_count=2,
            average_function_length=5.0,
        )
        architecture = ArchitectureScore(
            overall_score=0.8,
            layering_score=0.8,
            dependency_management_score=1.0,
            pattern_usage_score=0.7,
            coupling_estimate=0.1,
            domain="backend",
        )
        security = SecurityAudit(
            overall_score=1.0,
            injection_risk_found=False,
            hardcoded_secrets_found=False,
            weak_auth_pattern_found=False,
            dependency_risk_noted=False,
        )
        performance = PerformanceAudit(
            overall_score=1.0,
            inefficient_loop_patterns=0,
            memory_risk_patterns=0,
            domain="backend",
        )
        result = ReviewResult(
            project="demo",
            code_quality=quality,
            architecture=architecture,
            security=security,
            performance=performance,
            maintainability_score=0.9,
            test_coverage_estimate=0.5,
            has_documentation=True,
            meets_standards=True,
            follows_frontier_practices=True,
            ready_for_production=True,
            overall_score=0.9,
            summary="looks good",
        )
        assert result.project == "demo"
        assert result.ready_for_production is True
        assert result.blocking_issues == ()

    def test_dataclasses_are_frozen(self) -> None:
        quality = CodeQualityScore(
            overall_score=0.9,
            cyclomatic_complexity=2.0,
            max_cyclomatic_complexity=3,
            naming_convention_score=1.0,
            modularity_score=1.0,
            function_count=2,
            average_function_length=5.0,
        )
        with pytest.raises(Exception):
            quality.overall_score = 0.1  # type: ignore[misc]


# --------------------------------------------------------------------
# Per-dimension scoring tests
# --------------------------------------------------------------------


class TestCodeQualityReview:
    def test_good_code_scores_well(self, reviewer: ProfessionalCodeReviewer) -> None:
        score = reviewer._review_code_quality(GOOD_CODE)
        assert isinstance(score, CodeQualityScore)
        assert score.overall_score > 0.6
        assert score.function_count >= 3

    def test_bad_naming_flagged(self, reviewer: ProfessionalCodeReviewer) -> None:
        score = reviewer._review_code_quality(BAD_CODE)
        assert any("BadName" in issue for issue in score.issues)

    def test_unparseable_code_returns_low_score(self, reviewer: ProfessionalCodeReviewer) -> None:
        score = reviewer._review_code_quality(UNPARSEABLE_CODE)
        assert score.overall_score <= 0.3
        assert score.issues


class TestArchitectureReview:
    def test_good_code_has_layering(self, reviewer: ProfessionalCodeReviewer) -> None:
        score = reviewer._review_architecture(GOOD_CODE, "backend")
        assert isinstance(score, ArchitectureScore)
        assert score.domain == "backend"
        assert score.overall_score > 0.5

    def test_unstructured_code_flagged(self, reviewer: ProfessionalCodeReviewer) -> None:
        score = reviewer._review_architecture("x = 1\ny = 2\nprint(x + y)\n", "general")
        assert score.layering_score < 0.5
        assert score.issues


class TestSecurityReview:
    def test_clean_code_has_no_findings(self, reviewer: ProfessionalCodeReviewer) -> None:
        audit = reviewer._review_security(GOOD_CODE)
        assert audit.injection_risk_found is False
        assert audit.hardcoded_secrets_found is False
        assert audit.overall_score >= 0.7

    def test_bad_code_flags_injection_and_secrets(self, reviewer: ProfessionalCodeReviewer) -> None:
        audit = reviewer._review_security(BAD_CODE)
        assert audit.injection_risk_found is True
        assert audit.hardcoded_secrets_found is True
        assert audit.overall_score < 0.5
        assert audit.findings


class TestPerformanceReview:
    def test_nested_loops_flagged(self, reviewer: ProfessionalCodeReviewer) -> None:
        audit = reviewer._review_performance(BAD_CODE, "backend")
        assert audit.inefficient_loop_patterns > 0
        assert audit.overall_score < 1.0

    def test_simple_code_scores_well(self, reviewer: ProfessionalCodeReviewer) -> None:
        audit = reviewer._review_performance(GOOD_CODE, "backend")
        assert audit.overall_score > 0.7


class TestMaintainabilityAndVerification:
    def test_maintainability_score_in_range(self, reviewer: ProfessionalCodeReviewer) -> None:
        score = reviewer._review_maintainability(GOOD_CODE)
        assert 0.0 <= score <= 1.0

    def test_test_coverage_estimate(self, reviewer: ProfessionalCodeReviewer) -> None:
        coverage = reviewer._verify_test_coverage(GOOD_CODE)
        assert 0.0 <= coverage <= 1.0
        assert coverage > 0.0

    def test_test_coverage_zero_when_no_tests(self, reviewer: ProfessionalCodeReviewer) -> None:
        coverage = reviewer._verify_test_coverage(BAD_CODE)
        assert coverage == 0.0

    def test_documentation_detection(self, reviewer: ProfessionalCodeReviewer) -> None:
        assert reviewer._verify_documentation(GOOD_CODE) is True
        assert reviewer._verify_documentation(BAD_CODE) is False

    def test_standards_check(self, reviewer: ProfessionalCodeReviewer) -> None:
        assert reviewer._check_standards(GOOD_CODE, "backend") is True

    def test_frontier_practices_check(self, reviewer: ProfessionalCodeReviewer) -> None:
        assert reviewer._check_frontier_practices(GOOD_CODE, "backend") is True
        assert reviewer._check_frontier_practices(BAD_CODE, "backend") is False

    def test_ready_for_production(self, reviewer: ProfessionalCodeReviewer) -> None:
        assert reviewer._ready_for_production(GOOD_CODE, "demo") is True
        assert reviewer._ready_for_production(BAD_CODE, "demo") is False


# --------------------------------------------------------------------
# Integration tests
# --------------------------------------------------------------------


class TestFullReviewIntegration:
    def test_review_good_code_end_to_end(self, reviewer: ProfessionalCodeReviewer) -> None:
        result = reviewer.review_for_deployment("demo-backend-service", GOOD_CODE)
        assert isinstance(result, ReviewResult)
        assert result.project == "demo-backend-service"
        assert result.ready_for_production is True
        assert result.blocking_issues == ()
        assert 0.0 <= result.overall_score <= 1.0
        assert result.summary

    def test_review_bad_code_end_to_end(self, reviewer: ProfessionalCodeReviewer) -> None:
        result = reviewer.review_for_deployment("demo-backend-service", BAD_CODE)
        assert result.ready_for_production is False
        assert result.blocking_issues
        assert result.security.injection_risk_found is True
        assert result.overall_score < 0.6

    def test_review_unparseable_code_end_to_end(self, reviewer: ProfessionalCodeReviewer) -> None:
        result = reviewer.review_for_deployment("demo", UNPARSEABLE_CODE)
        assert result.ready_for_production is False
        assert result.code_quality.overall_score <= 0.3
        assert result.architecture.overall_score <= 0.3

    def test_domain_inference_flows_through(self, reviewer: ProfessionalCodeReviewer) -> None:
        result = reviewer.review_for_deployment("ml-training-pipeline", GOOD_CODE)
        assert result.architecture.domain == "ml"
        assert result.performance.domain == "ml"
