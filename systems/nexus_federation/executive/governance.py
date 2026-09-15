"""F9 Phase G: Policy Versioning + Escalation Governance.

All executive policy decisions become versioned, auditable, reversible,
authority-bounded, and evidence-linked. Escalation is the explicit
mechanism for actions or conditions beyond autonomous authority.

AUTOMATIC_POLICY_MUTATION = PROHIBITED in this phase: NEXUS may observe,
propose, compare, simulate -- never autonomously activate a policy version
that affects architecture or authority ceilings. Activation is always an
explicit, separately-authorized call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class PolicyType(str, Enum):
    """Closed vocabulary of governed policy domains."""
    ATTENTION = "ATTENTION"
    PRIORITY = "PRIORITY"
    MISSION_LIFECYCLE = "MISSION_LIFECYCLE"
    DEPENDENCY = "DEPENDENCY"
    SCHEDULING = "SCHEDULING"
    RESOURCE = "RESOURCE"
    CAPACITY = "CAPACITY"
    OUTCOME = "OUTCOME"
    RETRY = "RETRY"
    TIMEOUT = "TIMEOUT"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"
    ESCALATION = "ESCALATION"


class PolicyVersionStatus(str, Enum):
    """Closed vocabulary of policy version lifecycle states."""
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    ROLLED_BACK = "ROLLED_BACK"
    REJECTED = "REJECTED"


# Authority levels required to activate each policy type. Higher-consequence
# domains (financial/publication/architecture-adjacent) require higher
# authority than low-risk observability tuning. This mirrors the existing
# A1-A5 authority ceiling vocabulary used elsewhere in NEXUS.
POLICY_TYPE_REQUIRED_AUTHORITY = {
    PolicyType.ATTENTION: "A2",
    PolicyType.PRIORITY: "A2",
    PolicyType.MISSION_LIFECYCLE: "A3",
    PolicyType.DEPENDENCY: "A2",
    PolicyType.SCHEDULING: "A2",
    PolicyType.RESOURCE: "A3",
    PolicyType.CAPACITY: "A2",
    PolicyType.OUTCOME: "A2",
    PolicyType.RETRY: "A2",
    PolicyType.TIMEOUT: "A2",
    PolicyType.CIRCUIT_BREAKER: "A2",
    PolicyType.ESCALATION: "A3",
}

# Policy types where activation must NEVER weaken these hard gates,
# regardless of authority level -- these gates are structural, not policy.
STRUCTURALLY_PROTECTED_GATES = frozenset({
    "financial_execution_gate",
    "publication_gate",
    "security_boundary",
    "mission_authority_ceiling",
})


@dataclass(frozen=True)
class PolicyVersion:
    """Immutable policy version record."""
    policy_version_id: str
    policy_id: str
    version: int
    policy_type: PolicyType
    configuration: dict[str, Any]
    status: PolicyVersionStatus = PolicyVersionStatus.DRAFT
    effective_from: Optional[str] = None
    effective_until: Optional[str] = None
    change_reason: Optional[str] = None
    evidence_refs: list[str] = field(default_factory=list)
    provenance_refs: list[str] = field(default_factory=list)
    created_by: str = "nexus_kernel"
    authority_level: str = "A1"
    supersedes_version_id: Optional[str] = None
    rollback_target_id: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_version_id": self.policy_version_id,
            "policy_id": self.policy_id,
            "version": self.version,
            "policy_type": self.policy_type.value,
            "configuration": self.configuration,
            "status": self.status.value,
            "effective_from": self.effective_from,
            "effective_until": self.effective_until,
            "change_reason": self.change_reason,
            "evidence_refs": self.evidence_refs,
            "provenance_refs": self.provenance_refs,
            "created_by": self.created_by,
            "authority_level": self.authority_level,
            "supersedes_version_id": self.supersedes_version_id,
            "rollback_target_id": self.rollback_target_id,
            "created_at": self.created_at or datetime.now(timezone.utc).isoformat(),
        }


class EscalationClass(str, Enum):
    """Closed vocabulary of escalation triggers."""
    FINANCIAL_EXECUTION = "FINANCIAL_EXECUTION"
    EXTERNAL_PUBLICATION = "EXTERNAL_PUBLICATION"
    EXTERNAL_COMMUNICATION = "EXTERNAL_COMMUNICATION"
    DESTRUCTIVE_OPERATION = "DESTRUCTIVE_OPERATION"
    SECURITY_SENSITIVE_ACTION = "SECURITY_SENSITIVE_ACTION"
    ARCHITECTURE_MIGRATION = "ARCHITECTURE_MIGRATION"
    RESOURCE_BUDGET_EXCEEDED = "RESOURCE_BUDGET_EXCEEDED"
    AUTHORITY_CEILING_EXCEEDED = "AUTHORITY_CEILING_EXCEEDED"
    HIGH_IMPACT_CONTRADICTION = "HIGH_IMPACT_CONTRADICTION"
    PERSISTENT_INSTITUTION_FAILURE = "PERSISTENT_INSTITUTION_FAILURE"
    DATA_INTEGRITY_RISK = "DATA_INTEGRITY_RISK"
    UNKNOWN_HIGH_CONSEQUENCE = "UNKNOWN_HIGH_CONSEQUENCE"


class EscalationSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EscalationStatus(str, Enum):
    """Closed vocabulary of escalation lifecycle states."""
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RESOLVED = "RESOLVED"
    EXPIRED = "EXPIRED"
    WITHDRAWN = "WITHDRAWN"


@dataclass(frozen=True)
class EscalationOption:
    """A single bounded option presented in an escalation, with its consequence."""
    option_id: str
    label: str
    consequence: str
    risk: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "option_id": self.option_id,
            "label": self.label,
            "consequence": self.consequence,
            "risk": self.risk,
        }


@dataclass(frozen=True)
class Escalation:
    """Immutable escalation creation record (status mutated via store, history preserved)."""
    escalation_id: str
    escalation_class: EscalationClass
    reason: str
    severity: EscalationSeverity = EscalationSeverity.MEDIUM
    mission_id: Optional[str] = None
    trigger_id: Optional[str] = None
    evidence_refs: list[str] = field(default_factory=list)
    provenance_refs: list[str] = field(default_factory=list)
    current_policy_version_id: Optional[str] = None
    requested_authority: Optional[str] = None
    current_authority_ceiling: Optional[str] = None
    recommended_options: list[EscalationOption] = field(default_factory=list)
    status: EscalationStatus = EscalationStatus.OPEN
    dedup_key: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "escalation_id": self.escalation_id,
            "escalation_class": self.escalation_class.value,
            "reason": self.reason,
            "severity": self.severity.value,
            "mission_id": self.mission_id,
            "trigger_id": self.trigger_id,
            "evidence_refs": self.evidence_refs,
            "provenance_refs": self.provenance_refs,
            "current_policy_version_id": self.current_policy_version_id,
            "requested_authority": self.requested_authority,
            "current_authority_ceiling": self.current_authority_ceiling,
            "recommended_options": [o.to_dict() for o in self.recommended_options],
            "status": self.status.value,
            "dedup_key": self.dedup_key or self.compute_dedup_key(),
            "created_at": self.created_at or datetime.now(timezone.utc).isoformat(),
        }

    def compute_dedup_key(self) -> str:
        """Semantic dedup key: same class + same mission + same trigger =>
        same escalation condition, must not flood the system with duplicates.
        """
        import hashlib
        basis = f"{self.escalation_class.value}|{self.mission_id}|{self.trigger_id}"
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()


# Authority ceiling ordering, low to high.
AUTHORITY_ORDER = ["A0", "A1", "A2", "A3", "A4", "A5"]


def authority_exceeds_ceiling(requested: str, ceiling: str) -> bool:
    """True if requested authority level exceeds the current ceiling."""
    try:
        return AUTHORITY_ORDER.index(requested) > AUTHORITY_ORDER.index(ceiling)
    except ValueError:
        # Unknown authority tokens are conservatively treated as exceeding.
        return True


# Actions that are PERMANENTLY prohibited regardless of any policy version
# or escalation approval -- these are structural, not governed by policy.
PERMANENTLY_PROHIBITED_ACTIONS = frozenset({
    "PLACE_LIVE_ORDER",
    "EXECUTE_TRADE",
    "TRANSFER_FUNDS",
    "PUBLISH",
    "UPLOAD_TO_PLATFORM",
    "SEND_EXTERNAL_COMMUNICATION",
})


def evaluate_authority_request(
    requested_action: str,
    requested_authority: str,
    current_ceiling: str,
) -> tuple[bool, Optional[EscalationClass], str]:
    """Evaluate whether an action can proceed under current authority.

    Returns (allowed, escalation_class_if_any, reason).
    PERMANENTLY_PROHIBITED_ACTIONS can never be allowed, no matter the
    authority level or any escalation resolution -- NEXUS cannot execute
    trades or publish content under any circumstance in this phase.
    """
    if requested_action in PERMANENTLY_PROHIBITED_ACTIONS:
        if requested_action in ("PLACE_LIVE_ORDER", "EXECUTE_TRADE", "TRANSFER_FUNDS"):
            return False, EscalationClass.FINANCIAL_EXECUTION, (
                f"{requested_action} is permanently prohibited (financial execution gate)"
            )
        if requested_action in ("PUBLISH", "UPLOAD_TO_PLATFORM"):
            return False, EscalationClass.EXTERNAL_PUBLICATION, (
                f"{requested_action} is permanently prohibited (publication gate)"
            )
        return False, EscalationClass.EXTERNAL_COMMUNICATION, (
            f"{requested_action} is permanently prohibited (external communication gate)"
        )

    if authority_exceeds_ceiling(requested_authority, current_ceiling):
        return False, EscalationClass.AUTHORITY_CEILING_EXCEEDED, (
            f"requested authority {requested_authority} exceeds ceiling {current_ceiling}"
        )

    return True, None, "within authority ceiling"


def default_escalation_options(escalation_class: EscalationClass) -> list[EscalationOption]:
    """Bounded default options per escalation class, with explicit consequences."""
    common_defer = EscalationOption(
        option_id="defer",
        label="Defer",
        consequence="Mission remains WAITING_AUTHORIZATION; no action taken now.",
        risk="Delay; no immediate risk.",
    )
    common_cancel = EscalationOption(
        option_id="cancel",
        label="Cancel mission",
        consequence="Mission transitions to CANCELLED; objective not pursued.",
        risk="Lost opportunity if objective was time-sensitive.",
    )
    reject = EscalationOption(
        option_id="reject",
        label="Reject action",
        consequence="Requested action is permanently denied for this mission instance.",
        risk="None to NEXUS; may block downstream objective.",
    )

    if escalation_class in (EscalationClass.FINANCIAL_EXECUTION, EscalationClass.EXTERNAL_PUBLICATION):
        return [
            reject,
            common_defer,
            common_cancel,
        ]

    if escalation_class == EscalationClass.RESOURCE_BUDGET_EXCEEDED:
        return [
            reject,
            EscalationOption(
                option_id="approve_budget_increase",
                label="Approve one-time budget increase",
                consequence="Mission proceeds with an explicitly authorized higher resource ceiling for this instance only.",
                risk="Resource contention with other missions; does not change the standing policy.",
            ),
            common_defer,
            common_cancel,
        ]

    if escalation_class == EscalationClass.HIGH_IMPACT_CONTRADICTION:
        return [
            EscalationOption(
                option_id="request_more_evidence",
                label="Request additional evidence",
                consequence="Delegate a bounded follow-up research mission to resolve the contradiction.",
                risk="Additional resource cost; may not resolve if evidence remains genuinely contradictory.",
            ),
            common_defer,
            reject,
        ]

    if escalation_class == EscalationClass.PERSISTENT_INSTITUTION_FAILURE:
        return [
            EscalationOption(
                option_id="approve_alternate_route",
                label="Approve alternate institution route (if one exists)",
                consequence="Reroute mission to an alternate institution with equivalent capability.",
                risk="Alternate institution may have different quality/reliability characteristics.",
            ),
            common_defer,
            common_cancel,
        ]

    return [reject, common_defer, common_cancel]
