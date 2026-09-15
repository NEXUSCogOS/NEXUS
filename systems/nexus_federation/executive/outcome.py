"""NEXUS Executive Outcome Evaluation.

F9 hardening: formal outcome classification and learning.

Every mission's result is classified. Success is NOT "code exited zero",
it's "did we achieve the stated success criteria?".

Classification is deterministic, auditable.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class OutcomeClass(str, Enum):
    """Mission outcome classification (F9.E closed vocabulary)."""

    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    FAILED = "FAILED"
    INVALIDATED = "INVALIDATED"
    NO_ACTION_REQUIRED = "NO_ACTION_REQUIRED"


class FailureClass(str, Enum):
    """Mission failure classification (F9.E closed vocabulary)."""
    TRANSIENT_DEPENDENCY_FAILURE = "TRANSIENT_DEPENDENCY_FAILURE"
    PERSISTENT_DEPENDENCY_FAILURE = "PERSISTENT_DEPENDENCY_FAILURE"
    INVALID_INPUT = "INVALID_INPUT"
    POLICY_REJECTION = "POLICY_REJECTION"
    AUTHORITY_REJECTION = "AUTHORITY_REJECTION"
    RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"
    TIMEOUT = "TIMEOUT"
    INSTITUTION_UNAVAILABLE = "INSTITUTION_UNAVAILABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INTERNAL_DEFECT = "INTERNAL_DEFECT"
    UNKNOWN = "UNKNOWN"


class DownstreamUsefulness(str, Enum):
    """How outcome was used downstream (F9.E bounded learning)."""
    USED_FOR_SYNTHESIS = "USED_FOR_SYNTHESIS"
    USED_FOR_ROUTING = "USED_FOR_ROUTING"
    USED_FOR_PRODUCTION = "USED_FOR_PRODUCTION"
    USED_FOR_MONITORING = "USED_FOR_MONITORING"
    NO_DOWNSTREAM_USE = "NO_DOWNSTREAM_USE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class OutcomeEvaluation:
    """Immutable outcome evaluation record (F9.E append-only model).

    Captured at mission terminal state.
    Linked to evidence, provenance, success criteria.
    """

    outcome_id: str
    mission_id: str
    delegation_id: str
    outcome_class: OutcomeClass
    evaluated_at: datetime
    evaluator: str = "nexus_kernel"
    objective: Optional[str] = None
    success_criteria: list[str] = field(default_factory=list)
    criteria_met: list[str] = field(default_factory=list)
    criteria_unmet: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    provenance_refs: list[str] = field(default_factory=list)
    limitations: Optional[str] = None
    uncertainty: Optional[float] = None
    resource_actuals: dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    failure_class: Optional[FailureClass] = None
    downstream_usefulness: Optional[DownstreamUsefulness] = None
    supersedes_outcome_id: Optional[str] = None
    policy_version: str = "F9.0"

    def to_dict(self) -> dict[str, Any]:
        """Convert to persistence dict."""
        return {
            "outcome_id": self.outcome_id,
            "mission_id": self.mission_id,
            "delegation_id": self.delegation_id,
            "outcome_class": self.outcome_class.value,
            "evaluated_at": self.evaluated_at.isoformat(),
            "evaluator": self.evaluator,
            "objective": self.objective,
            "success_criteria": self.success_criteria,
            "criteria_met": self.criteria_met,
            "criteria_unmet": self.criteria_unmet,
            "evidence_refs": self.evidence_refs,
            "provenance_refs": self.provenance_refs,
            "limitations": self.limitations,
            "uncertainty": self.uncertainty,
            "resource_actuals": self.resource_actuals,
            "retry_count": self.retry_count,
            "failure_class": self.failure_class.value if self.failure_class else None,
            "downstream_usefulness": self.downstream_usefulness.value if self.downstream_usefulness else None,
            "supersedes_outcome_id": self.supersedes_outcome_id,
            "policy_version": self.policy_version,
        }


@dataclass
class SourcePerformance:
    """Summary statistics for institution performance (bounded learning F9.E)."""
    institution_id: str
    total_missions: int = 0
    successful_missions: int = 0
    failed_missions: int = 0
    avg_resource_cost: float = 0.0
    reliability: float = 0.0


class ObservationType(str, Enum):
    """Learning event observation types."""
    ROUTING_EFFECTIVENESS = "ROUTING_EFFECTIVENESS"
    INSTITUTION_RELIABILITY = "INSTITUTION_RELIABILITY"
    RESOURCE_ESTIMATE_ERROR = "RESOURCE_ESTIMATE_ERROR"
    PRIORITY_OUTCOME = "PRIORITY_OUTCOME"
    ATTENTION_OUTCOME = "ATTENTION_OUTCOME"
    DOWNSTREAM_USEFULNESS = "DOWNSTREAM_USEFULNESS"


class LearningEventStatus(str, Enum):
    """Learning event status (F9.E bounded learning)."""
    OBSERVED = "OBSERVED"
    INSUFFICIENT_SAMPLE_SIZE = "INSUFFICIENT_SAMPLE_SIZE"
    CALIBRATION_CANDIDATE = "CALIBRATION_CANDIDATE"
    POLICY_PROPOSAL_CREATED = "POLICY_PROPOSAL_CREATED"
    DISMISSED = "DISMISSED"


@dataclass(frozen=True)
class LearningEvent:
    """Immutable learning observation record (F9.E)."""
    learning_event_id: str
    source_mission_id: str
    observation_type: ObservationType
    observed_value: Optional[float] = None
    expected_value: Optional[float] = None
    difference: Optional[float] = None
    evidence_refs: list[str] = field(default_factory=list)
    confidence_basis: Optional[str] = None
    recommended_policy: Optional[str] = None
    recommended_change: Optional[str] = None
    sample_size: Optional[int] = None
    status: LearningEventStatus = LearningEventStatus.OBSERVED
    created_at: Optional[datetime] = None
    policy_version: str = "F9.0"

    def to_dict(self) -> dict[str, Any]:
        """Convert to persistence dict."""
        return {
            "learning_event_id": self.learning_event_id,
            "source_mission_id": self.source_mission_id,
            "observation_type": self.observation_type.value,
            "observed_value": self.observed_value,
            "expected_value": self.expected_value,
            "difference": self.difference,
            "evidence_refs": self.evidence_refs,
            "confidence_basis": self.confidence_basis,
            "recommended_policy": self.recommended_policy,
            "recommended_change": self.recommended_change,
            "sample_size": self.sample_size,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else datetime.now(timezone.utc).isoformat(),
            "policy_version": self.policy_version,
        }


@dataclass(frozen=True)
class PolicyProposal:
    """Immutable policy change proposal (F9.E bounded learning)."""
    proposal_id: str
    target_policy: str
    current_version: str
    suggested_change: str
    evidence_basis: Optional[str] = None
    sample_size: Optional[int] = None
    risk: Optional[str] = None
    status: str = "PROPOSED"
    created_at: Optional[datetime] = None
    policy_version: str = "F9.0"

    def to_dict(self) -> dict[str, Any]:
        """Convert to persistence dict."""
        return {
            "proposal_id": self.proposal_id,
            "target_policy": self.target_policy,
            "current_version": self.current_version,
            "suggested_change": self.suggested_change,
            "evidence_basis": self.evidence_basis,
            "sample_size": self.sample_size,
            "risk": self.risk,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else datetime.now(timezone.utc).isoformat(),
            "policy_version": self.policy_version,
        }
