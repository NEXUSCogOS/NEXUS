"""Tests for autonomy_system.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from systems.engineering_studio.studio_v3.core.autonomy_system import (
    AutonomousDecisionMaker,
    AutonomyLevel,
    Decision,
    DecisionOutcome,
    EscalationFramework,
    EscalationReason,
    GuardrailPolicy,
    GuardrailViolation,
)
from systems.engineering_studio.studio_v3.core.project_management import AuthorityLevel


def make_decision(**overrides):
    defaults = dict(
        decision_type="code_style_changes",
        description="Reformat module X",
        risk_level="LOW",
        affects_core=False,
        dependent_count=0,
        novel=False,
        within_expertise=True,
    )
    defaults.update(overrides)
    return Decision(**defaults)


# ── Escalation detection ────────────────────────────────────────────────

def test_routine_low_risk_does_not_escalate():
    framework = EscalationFramework()
    decision = make_decision()
    assert framework.should_escalate(decision) is False


def test_high_risk_escalates():
    framework = EscalationFramework()
    decision = make_decision(decision_type="new_features", risk_level="HIGH")
    assert framework.should_escalate(decision) is True


def test_affects_core_escalates_with_core_system_reason():
    framework = EscalationFramework()
    decision = make_decision(affects_core=True)
    reasons = framework._escalation_reasons(decision)
    assert EscalationReason.CORE_SYSTEM in reasons


def test_novel_decision_escalates():
    framework = EscalationFramework()
    decision = make_decision(novel=True)
    reasons = framework._escalation_reasons(decision)
    assert EscalationReason.NOVEL_DECISION in reasons


def test_outside_expertise_escalates():
    framework = EscalationFramework()
    decision = make_decision(within_expertise=False)
    reasons = framework._escalation_reasons(decision)
    assert EscalationReason.OUTSIDE_EXPERTISE in reasons


def test_unknown_decision_type_flags_context_missing():
    framework = EscalationFramework()
    decision = make_decision(decision_type="something_unheard_of")
    reasons = framework._escalation_reasons(decision)
    assert EscalationReason.CONTEXT_MISSING in reasons


# ── Authority assessment ────────────────────────────────────────────────

def test_code_style_is_autonomous():
    framework = EscalationFramework()
    decision = make_decision(decision_type="code_style_changes")
    assert framework.assess_authority_required(decision) == AuthorityLevel.AUTONOMOUS


def test_bug_fix_requires_tests_for_autonomy():
    framework = EscalationFramework()
    untested = make_decision(decision_type="bug_fixes", tested=False)
    tested = make_decision(decision_type="bug_fixes", tested=True)
    assert framework.assess_authority_required(untested) == AuthorityLevel.COMPLEX
    assert framework.assess_authority_required(tested) == AuthorityLevel.AUTONOMOUS


def test_performance_optimization_requires_5pct_improvement():
    framework = EscalationFramework()
    small = make_decision(decision_type="performance_optimization", performance_delta_pct=2.0)
    big = make_decision(decision_type="performance_optimization", performance_delta_pct=9.0)
    assert framework.assess_authority_required(small) == AuthorityLevel.COMPLEX
    assert framework.assess_authority_required(big) == AuthorityLevel.AUTONOMOUS


def test_dependency_updates_require_security_audit():
    framework = EscalationFramework()
    unaudited = make_decision(decision_type="dependency_updates", security_audit_passed=False)
    audited = make_decision(decision_type="dependency_updates", security_audit_passed=True)
    assert framework.assess_authority_required(unaudited) == AuthorityLevel.COMPLEX
    assert framework.assess_authority_required(audited) == AuthorityLevel.AUTONOMOUS


def test_breaking_changes_requires_review():
    framework = EscalationFramework()
    decision = make_decision(decision_type="breaking_changes")
    assert framework.assess_authority_required(decision) == AuthorityLevel.REQUIRES_REVIEW


def test_architecture_changes_are_complex():
    framework = EscalationFramework()
    decision = make_decision(decision_type="architecture_changes")
    assert framework.assess_authority_required(decision) == AuthorityLevel.COMPLEX


def test_critical_risk_forces_handoff():
    framework = EscalationFramework()
    decision = make_decision(decision_type="code_style_changes", risk_level="CRITICAL")
    assert framework.assess_authority_required(decision) == AuthorityLevel.REQUIRES_HANDOFF


def test_affects_core_forces_at_least_review():
    framework = EscalationFramework()
    decision = make_decision(decision_type="code_style_changes", affects_core=True)
    assert framework.assess_authority_required(decision) == AuthorityLevel.REQUIRES_REVIEW


# ── Decision making ─────────────────────────────────────────────────────

def test_autonomous_routine_decision_executes():
    maker = AutonomousDecisionMaker()
    decision = make_decision(decision_type="documentation_updates")
    outcome = maker.make_decision(decision)
    assert isinstance(outcome, DecisionOutcome)
    assert outcome.executed is True
    assert outcome.escalated is False
    assert outcome.autonomy_level == AutonomyLevel.ROUTINE


def test_complex_decision_escalates_via_make_decision():
    maker = AutonomousDecisionMaker()
    decision = make_decision(decision_type="new_features", risk_level="MEDIUM")
    outcome = maker.make_decision(decision)
    assert outcome.executed is False
    assert outcome.escalated is True
    assert "escalation_package" in outcome.detail


def test_system_threatening_decision_never_executes():
    maker = AutonomousDecisionMaker()
    decision = make_decision(decision_type="code_style_changes", affects_core=True, risk_level="CRITICAL")
    outcome = maker.make_decision(decision)
    assert outcome.executed is False
    assert outcome.autonomy_level == AutonomyLevel.SYSTEM_THREATENING


def test_novel_decision_escalates_even_if_matrix_allows_autonomy():
    maker = AutonomousDecisionMaker()
    decision = make_decision(decision_type="documentation_updates", novel=True)
    outcome = maker.make_decision(decision)
    assert outcome.escalated is True
    assert outcome.autonomy_level == AutonomyLevel.NOVEL


def test_execution_log_records_outcomes():
    maker = AutonomousDecisionMaker()
    maker.make_decision(make_decision(decision_type="code_style_changes"))
    maker.make_decision(make_decision(decision_type="new_features"))
    assert len(maker.execution_log) == 2


def test_prepare_escalation_returns_package_dict():
    maker = AutonomousDecisionMaker()
    decision = make_decision(decision_type="breaking_changes")
    package = maker._prepare_escalation(decision)
    assert package["decision_type"] == "breaking_changes"
    assert "reasons" in package


# ── Guardrails ───────────────────────────────────────────────────────────

def test_guardrail_blocks_deleting_audit_trail():
    policy = GuardrailPolicy()
    try:
        policy.check_action("delete", "audit_trail")
        assert False, "expected GuardrailViolation"
    except GuardrailViolation:
        pass


def test_guardrail_blocks_modifying_core_manifest_metrics():
    policy = GuardrailPolicy()
    try:
        policy.check_action("modify", "core_manifest_metrics")
        assert False, "expected GuardrailViolation"
    except GuardrailViolation:
        pass


def test_guardrail_allows_non_protected_actions():
    policy = GuardrailPolicy()
    policy.check_action("delete", "scratch_file")  # should not raise
    policy.check_action("modify", "code_style_changes")  # should not raise


def test_execution_blocked_when_bug_fix_untested():
    maker = AutonomousDecisionMaker()
    decision = make_decision(decision_type="bug_fixes", tested=False)
    outcome = maker.make_decision(decision)
    assert outcome.executed is False
    assert outcome.escalated is True


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
