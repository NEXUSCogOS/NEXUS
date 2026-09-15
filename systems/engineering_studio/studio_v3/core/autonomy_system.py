"""Autonomy and decision-making framework for the Elite Autonomous Engineering Studio.

Determines when the system can act autonomously versus when it must escalate
to a human. Enforces the Decision Authority Matrix and a set of hard
guardrails around destructive/irreversible operations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from .project_management import AuthorityLevel


# ════════════════════════════════════════════════════════════════════════════
# ENUMS
# ════════════════════════════════════════════════════════════════════════════

class AutonomyLevel(Enum):
    """How much latitude the system has to act on a decision"""
    ROUTINE = auto()              # Low risk, well-understood, fully autonomous
    COMPLEX = auto()               # Higher risk / broader impact, needs elevated review
    NOVEL = auto()                  # No precedent, outside trained expertise
    SYSTEM_THREATENING = auto()     # Could damage core system integrity
    REQUIRES_HANDOFF = auto()       # Must be fully handed to a human


class EscalationReason(Enum):
    """Why a decision was escalated"""
    CONTEXT_MISSING = auto()
    RISK_TOO_HIGH = auto()
    OUTSIDE_EXPERTISE = auto()
    NOVEL_DECISION = auto()
    CORE_SYSTEM = auto()


RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


# ════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ════════════════════════════════════════════════════════════════════════════

class GuardrailViolation(RuntimeError):
    """Raised when a decision would violate a hard guardrail"""


# ════════════════════════════════════════════════════════════════════════════
# CORE ENTITIES
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Decision:
    """A candidate decision the system is evaluating for autonomous action"""

    decision_type: str
    description: str
    risk_level: str = "LOW"                 # LOW, MEDIUM, HIGH, CRITICAL
    affects_core: bool = False
    dependent_count: int = 0
    novel: bool = False
    within_expertise: bool = True
    decision_id: UUID = field(default_factory=uuid4)

    # Optional verification/context fields used by guardrail checks
    tested: bool = False
    performance_delta_pct: float = 0.0
    security_audit_passed: bool = False
    context: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.risk_level not in RISK_LEVELS:
            raise ValueError(
                f"risk_level must be one of {RISK_LEVELS}, got {self.risk_level!r}"
            )
        if self.dependent_count < 0:
            raise ValueError("dependent_count cannot be negative")


@dataclass
class DecisionOutcome:
    """Result of processing a Decision through the autonomy framework"""

    decision_id: UUID
    executed: bool
    escalated: bool
    authority_required: AuthorityLevel
    autonomy_level: AutonomyLevel
    escalation_reasons: List[EscalationReason] = field(default_factory=list)
    detail: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": str(self.decision_id),
            "executed": self.executed,
            "escalated": self.escalated,
            "authority_required": self.authority_required.name,
            "autonomy_level": self.autonomy_level.name,
            "escalation_reasons": [r.name for r in self.escalation_reasons],
            "detail": self.detail,
            "timestamp": self.timestamp.isoformat(),
        }


# ════════════════════════════════════════════════════════════════════════════
# DECISION AUTHORITY MATRIX
# ════════════════════════════════════════════════════════════════════════════
#
# Static mapping of decision_type -> required authority. Some entries are
# conditionally AUTONOMOUS ("if tested" / "if >5% improvement" / "if security
# audit passes"); the condition is enforced in EscalationFramework via the
# CONDITIONAL_REQUIREMENTS table below, falling back to COMPLEX when unmet.

DECISION_AUTHORITY_MATRIX: Dict[str, AuthorityLevel] = {
    "code_style_changes": AuthorityLevel.AUTONOMOUS,
    "bug_fixes": AuthorityLevel.AUTONOMOUS,                 # if tested
    "performance_optimization": AuthorityLevel.AUTONOMOUS,  # if >5% improvement
    "new_features": AuthorityLevel.COMPLEX,
    "architecture_changes": AuthorityLevel.COMPLEX,
    "dependency_updates": AuthorityLevel.AUTONOMOUS,        # if security audit passes
    "major_refactoring": AuthorityLevel.COMPLEX,
    "new_testing_strategy": AuthorityLevel.AUTONOMOUS,
    "documentation_updates": AuthorityLevel.AUTONOMOUS,
    "deployment_procedures": AuthorityLevel.COMPLEX,
    "security_changes": AuthorityLevel.COMPLEX,
    "breaking_changes": AuthorityLevel.REQUIRES_REVIEW,
}

# decision_type -> callable(Decision) -> bool. When present, the AUTONOMOUS
# grant from the matrix only holds if this predicate is satisfied; otherwise
# authority downgrades to COMPLEX.
CONDITIONAL_REQUIREMENTS = {
    "bug_fixes": lambda d: d.tested,
    "performance_optimization": lambda d: d.performance_delta_pct > 5.0,
    "dependency_updates": lambda d: d.security_audit_passed,
}


# ════════════════════════════════════════════════════════════════════════════
# GUARDRAILS
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class GuardrailPolicy:
    """Hard constraints the autonomy framework will never bypass"""

    cannot_delete: tuple = (
        "audit_trail",
        "completed_projects",
        "learned_procedures",
    )
    cannot_modify: tuple = (
        "core_manifest_metrics",
        "historical_audit_entries",
    )
    must_verify: tuple = (
        "all_code",
        "all_tests_passing",
        "all_metrics_in_range",
    )
    must_have: tuple = (
        "complete_audit_trail",
        "passing_tests",
        "documentation",
        "sign_off",
    )

    def check_action(self, action: str, target: str) -> None:
        """Raise GuardrailViolation if `action` on `target` is forbidden.

        action is one of: 'delete', 'modify'
        target is a guardrail-protected resource name (e.g. 'audit_trail')
        """
        if action == "delete" and target in self.cannot_delete:
            raise GuardrailViolation(
                f"Cannot delete protected resource: {target}"
            )
        if action == "modify" and target in self.cannot_modify:
            raise GuardrailViolation(
                f"Cannot modify protected resource: {target}"
            )

    def verify_execution_readiness(self, decision: "Decision") -> List[str]:
        """Return a list of unmet 'must_have' requirements for executing `decision`.

        Empty list means all requirements are satisfied (as far as can be
        determined from decision.context).
        """
        ctx = decision.context
        missing = []
        if not ctx.get("complete_audit_trail", True):
            missing.append("complete_audit_trail")
        if decision.decision_type in ("bug_fixes",) and not decision.tested:
            missing.append("passing_tests")
        if not ctx.get("documentation", True):
            missing.append("documentation")
        if ctx.get("sign_off_required", False) and not ctx.get("sign_off", False):
            missing.append("sign_off")
        return missing


DEFAULT_GUARDRAILS = GuardrailPolicy()


# ════════════════════════════════════════════════════════════════════════════
# ESCALATION FRAMEWORK
# ════════════════════════════════════════════════════════════════════════════

class EscalationFramework:
    """Determines whether a Decision must escalate to a human, and to what
    authority level, then routes it accordingly."""

    def __init__(self, guardrails: GuardrailPolicy = DEFAULT_GUARDRAILS) -> None:
        self.guardrails = guardrails

    def should_escalate(self, decision: Decision) -> bool:
        """True if any escalation trigger fires for this decision."""
        return len(self._escalation_reasons(decision)) > 0

    def _escalation_reasons(self, decision: Decision) -> List[EscalationReason]:
        reasons: List[EscalationReason] = []

        if decision.affects_core:
            reasons.append(EscalationReason.CORE_SYSTEM)

        if decision.risk_level in ("HIGH", "CRITICAL"):
            reasons.append(EscalationReason.RISK_TOO_HIGH)

        if not decision.within_expertise:
            reasons.append(EscalationReason.OUTSIDE_EXPERTISE)

        if decision.novel:
            reasons.append(EscalationReason.NOVEL_DECISION)

        if decision.dependent_count > 0 and decision.risk_level != "LOW":
            reasons.append(EscalationReason.RISK_TOO_HIGH)

        # Missing required context (e.g. decision_type unknown to matrix)
        if decision.decision_type not in DECISION_AUTHORITY_MATRIX:
            reasons.append(EscalationReason.CONTEXT_MISSING)

        # de-duplicate while preserving order
        seen = set()
        deduped = []
        for r in reasons:
            if r not in seen:
                seen.add(r)
                deduped.append(r)
        return deduped

    def _raw_authority(self, decision: Decision) -> AuthorityLevel:
        """Authority level implied purely by the Decision Authority Matrix,
        including conditional downgrades."""
        base = DECISION_AUTHORITY_MATRIX.get(decision.decision_type)
        if base is None:
            # Unknown decision type: treat conservatively.
            return AuthorityLevel.REQUIRES_REVIEW

        if base is AuthorityLevel.AUTONOMOUS:
            predicate = CONDITIONAL_REQUIREMENTS.get(decision.decision_type)
            if predicate is not None and not predicate(decision):
                return AuthorityLevel.COMPLEX
        return base

    def assess_authority_required(self, decision: Decision) -> AuthorityLevel:
        """Public entry point: authority level required for this decision,
        factoring in both the matrix and risk/novelty/core-system overrides."""
        authority = self._raw_authority(decision)

        # Hard overrides regardless of matrix entry.
        if decision.affects_core:
            authority = self._escalate_authority(authority, AuthorityLevel.REQUIRES_REVIEW)
        if decision.risk_level == "CRITICAL":
            authority = self._escalate_authority(authority, AuthorityLevel.REQUIRES_HANDOFF)
        elif decision.risk_level == "HIGH":
            authority = self._escalate_authority(authority, AuthorityLevel.REQUIRES_REVIEW)
        if decision.novel or not decision.within_expertise:
            authority = self._escalate_authority(authority, AuthorityLevel.COMPLEX)

        return authority

    @staticmethod
    def _escalate_authority(current: AuthorityLevel, minimum: AuthorityLevel) -> AuthorityLevel:
        """Return whichever of current/minimum requires more oversight."""
        order = [
            AuthorityLevel.AUTONOMOUS,
            AuthorityLevel.COMPLEX,
            AuthorityLevel.REQUIRES_REVIEW,
            AuthorityLevel.REQUIRES_HANDOFF,
        ]
        return current if order.index(current) >= order.index(minimum) else minimum

    def handle_decision(self, decision: Decision) -> DecisionOutcome:
        """Route the decision: execute autonomously, or package it for escalation."""
        reasons = self._escalation_reasons(decision)
        authority = self.assess_authority_required(decision)
        autonomy_level = _autonomy_level_for(decision, authority)

        if reasons or authority is not AuthorityLevel.AUTONOMOUS:
            return DecisionOutcome(
                decision_id=decision.decision_id,
                executed=False,
                escalated=True,
                authority_required=authority,
                autonomy_level=autonomy_level,
                escalation_reasons=reasons,
                detail={"escalation_package": self._build_escalation_package(decision, reasons)},
            )

        missing = self.guardrails.verify_execution_readiness(decision)
        if missing:
            return DecisionOutcome(
                decision_id=decision.decision_id,
                executed=False,
                escalated=True,
                authority_required=authority,
                autonomy_level=autonomy_level,
                escalation_reasons=[EscalationReason.CONTEXT_MISSING],
                detail={"missing_requirements": missing},
            )

        return DecisionOutcome(
            decision_id=decision.decision_id,
            executed=True,
            escalated=False,
            authority_required=authority,
            autonomy_level=autonomy_level,
            escalation_reasons=[],
            detail={"message": "Decision approved for autonomous execution"},
        )

    def _build_escalation_package(self, decision: Decision, reasons: List[EscalationReason]) -> Dict[str, Any]:
        return {
            "decision_id": str(decision.decision_id),
            "decision_type": decision.decision_type,
            "description": decision.description,
            "risk_level": decision.risk_level,
            "affects_core": decision.affects_core,
            "dependent_count": decision.dependent_count,
            "reasons": [r.name for r in reasons],
            "recommended_authority": self.assess_authority_required(decision).name,
            "requested_at": datetime.now(timezone.utc).isoformat(),
        }


def _autonomy_level_for(decision: Decision, authority: AuthorityLevel) -> AutonomyLevel:
    """Map a Decision + resolved AuthorityLevel to an AutonomyLevel classification."""
    if decision.affects_core or decision.risk_level == "CRITICAL":
        return AutonomyLevel.SYSTEM_THREATENING
    if authority is AuthorityLevel.REQUIRES_HANDOFF:
        return AutonomyLevel.REQUIRES_HANDOFF
    if decision.novel or not decision.within_expertise:
        return AutonomyLevel.NOVEL
    if authority is AuthorityLevel.AUTONOMOUS:
        return AutonomyLevel.ROUTINE
    return AutonomyLevel.COMPLEX


# ════════════════════════════════════════════════════════════════════════════
# AUTONOMOUS DECISION MAKER
# ════════════════════════════════════════════════════════════════════════════

class AutonomousDecisionMaker:
    """High-level entry point: evaluate a Decision and either execute it
    autonomously or prepare it for human escalation."""

    def __init__(
        self,
        framework: Optional[EscalationFramework] = None,
        guardrails: GuardrailPolicy = DEFAULT_GUARDRAILS,
    ) -> None:
        self.framework = framework or EscalationFramework(guardrails=guardrails)
        self.guardrails = guardrails
        self.execution_log: List[DecisionOutcome] = []

    def make_decision(self, decision: Decision) -> DecisionOutcome:
        """Primary entry point. Assess, then either execute or escalate."""
        autonomy_level = self._assess_autonomy_level(decision)

        if self.framework.should_escalate(decision) or autonomy_level in (
            AutonomyLevel.SYSTEM_THREATENING,
            AutonomyLevel.REQUIRES_HANDOFF,
            AutonomyLevel.NOVEL,
        ):
            outcome = self._prepare_escalation_outcome(decision, autonomy_level)
        else:
            authority = self.framework.assess_authority_required(decision)
            if authority is AuthorityLevel.AUTONOMOUS:
                outcome = self._execute_decision(decision)
            else:
                outcome = self._prepare_escalation_outcome(decision, autonomy_level)

        self.execution_log.append(outcome)
        return outcome

    def _execute_decision(self, decision: Decision) -> DecisionOutcome:
        """Execute a decision that has cleared escalation checks and
        guardrail verification."""
        authority = self.framework.assess_authority_required(decision)
        autonomy_level = _autonomy_level_for(decision, authority)

        missing = self.guardrails.verify_execution_readiness(decision)
        if missing:
            return DecisionOutcome(
                decision_id=decision.decision_id,
                executed=False,
                escalated=True,
                authority_required=authority,
                autonomy_level=autonomy_level,
                escalation_reasons=[EscalationReason.CONTEXT_MISSING],
                detail={"missing_requirements": missing},
            )

        try:
            self.guardrails.check_action("modify", decision.decision_type)
        except GuardrailViolation as exc:
            return DecisionOutcome(
                decision_id=decision.decision_id,
                executed=False,
                escalated=True,
                authority_required=AuthorityLevel.REQUIRES_REVIEW,
                autonomy_level=AutonomyLevel.SYSTEM_THREATENING,
                escalation_reasons=[EscalationReason.CORE_SYSTEM],
                detail={"guardrail_violation": str(exc)},
            )

        return DecisionOutcome(
            decision_id=decision.decision_id,
            executed=True,
            escalated=False,
            authority_required=authority,
            autonomy_level=autonomy_level,
            escalation_reasons=[],
            detail={"message": f"Executed autonomously: {decision.decision_type}"},
        )

    def _prepare_escalation(self, decision: Decision) -> Dict[str, Any]:
        """Build the escalation package (for external notification systems)."""
        reasons = self.framework._escalation_reasons(decision)
        return self.framework._build_escalation_package(decision, reasons)

    def _prepare_escalation_outcome(self, decision: Decision, autonomy_level: AutonomyLevel) -> DecisionOutcome:
        package = self._prepare_escalation(decision)
        authority = self.framework.assess_authority_required(decision)
        reasons = self.framework._escalation_reasons(decision)
        return DecisionOutcome(
            decision_id=decision.decision_id,
            executed=False,
            escalated=True,
            authority_required=authority,
            autonomy_level=autonomy_level,
            escalation_reasons=reasons,
            detail={"escalation_package": package},
        )

    def _assess_autonomy_level(self, decision: Decision) -> AutonomyLevel:
        authority = self.framework.assess_authority_required(decision)
        return _autonomy_level_for(decision, authority)
