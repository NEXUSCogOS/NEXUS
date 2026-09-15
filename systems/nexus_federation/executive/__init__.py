"""NEXUS Executive Coordinator F9.

Composition layer that wraps the canonical FederationKernel with F9
executive cognition: attention, priority, mission planning, resource
governance, outcome evaluation, and autonomous orchestration.

Main entry point: executive.coordinator.ExecutiveCoordinator

The coordinator adds executive functions WITHOUT duplicating:
- ingress validation
- evidence resolution
- provenance
- state persistence
- institutional registry

All persistent operations flow through the canonical FederationKernel.

Components:
- coordinator: main composition layer (composes FederationKernel)
- attention: attention model (interest vs. importance)
- priority: priority assignment (when to act)
- resource_governance: budget enforcement
- outcome: outcome evaluation and learning

Deprecated (integrated into persistence/coordinator):
- mission: mission lifecycle (will use canonical delegation model)
- scheduler: scheduling (will use canonical delegation model)
- institution_capacity: capacity (will extend canonical registry)
"""

from executive.attention import (
    AttentionClass,
    AttentionFactors,
    AttentionSignal,
    classify_attention,
    compute_attention_score,
)
from executive.coordinator import ExecutiveCoordinator
from executive.mission_state import MissionState, validate_transition, is_terminal
from executive.dependency_semantics import DependencyType, detect_cycle
from executive.scheduler import ExecutiveScheduler
from executive.capacity import AvailabilityState, CircuitState, is_admissible
from executive.events import (
    EventType,
    EventStatus,
    ExecutiveEvent,
    EVENT_SCHEMA_VERSION,
    MAX_EVENT_ATTEMPTS,
    is_stale_event,
    is_future_dated,
)
from executive.memory import (
    EpisodeType,
    SemanticStatus,
    ProvenanceIntegrityStatus,
    SEMANTIC_PROMOTION_CLAIM_CLASSES,
    Episode,
    SemanticMemoryItem,
    is_eligible_for_semantic_promotion,
    similarity_score,
)
from executive.governance import (
    PolicyType,
    PolicyVersionStatus,
    PolicyVersion,
    EscalationClass,
    EscalationSeverity,
    EscalationStatus,
    EscalationOption,
    Escalation,
    AUTHORITY_ORDER,
    PERMANENTLY_PROHIBITED_ACTIONS,
    STRUCTURALLY_PROTECTED_GATES,
    authority_exceeds_ceiling,
    evaluate_authority_request,
    default_escalation_options,
)
from executive.reliability import (
    RetryDecision,
    RetryPolicy,
    DEFAULT_RETRY_POLICY,
    decide_retry,
    Lease,
    is_lease_expired,
    is_mission_timed_out,
    CircuitBreakerPolicy,
    DEFAULT_CIRCUIT_POLICY,
    next_circuit_state,
)
from executive.outcome import (
    OutcomeClass,
    FailureClass,
    DownstreamUsefulness,
    OutcomeEvaluation,
    SourcePerformance,
    ObservationType,
    LearningEventStatus,
    LearningEvent,
    PolicyProposal,
)
from executive.priority import PriorityClass, PriorityDecision, PriorityFactors
from executive.resource_governance import (
    DEFAULT_ANALYSIS_BUDGET,
    DEFAULT_EXECUTIVE_KERNEL_BUDGET,
    DEFAULT_MEDIA_PRODUCTION_BUDGET,
    DEFAULT_RESEARCH_BUDGET,
    ResourceBudget,
    ResourceUsage,
)

__all__ = [
    "ExecutiveCoordinator",
    "AttentionClass",
    "AttentionFactors",
    "AttentionSignal",
    "classify_attention",
    "compute_attention_score",
    "MissionState",
    "validate_transition",
    "is_terminal",
    "DependencyType",
    "detect_cycle",
    "ExecutiveScheduler",
    "OutcomeClass",
    "FailureClass",
    "DownstreamUsefulness",
    "OutcomeEvaluation",
    "SourcePerformance",
    "ObservationType",
    "LearningEventStatus",
    "LearningEvent",
    "PolicyProposal",
    "PriorityClass",
    "PriorityDecision",
    "PriorityFactors",
    "ResourceBudget",
    "ResourceUsage",
    "DEFAULT_ANALYSIS_BUDGET",
    "DEFAULT_RESEARCH_BUDGET",
    "DEFAULT_MEDIA_PRODUCTION_BUDGET",
    "DEFAULT_EXECUTIVE_KERNEL_BUDGET",
    "RetryDecision",
    "RetryPolicy",
    "DEFAULT_RETRY_POLICY",
    "decide_retry",
    "Lease",
    "is_lease_expired",
    "is_mission_timed_out",
    "CircuitBreakerPolicy",
    "DEFAULT_CIRCUIT_POLICY",
    "next_circuit_state",
    "PolicyType",
    "PolicyVersionStatus",
    "PolicyVersion",
    "EscalationClass",
    "EscalationSeverity",
    "EscalationStatus",
    "EscalationOption",
    "Escalation",
    "AUTHORITY_ORDER",
    "PERMANENTLY_PROHIBITED_ACTIONS",
    "STRUCTURALLY_PROTECTED_GATES",
    "authority_exceeds_ceiling",
    "evaluate_authority_request",
    "default_escalation_options",
    "EpisodeType",
    "SemanticStatus",
    "ProvenanceIntegrityStatus",
    "SEMANTIC_PROMOTION_CLAIM_CLASSES",
    "Episode",
    "SemanticMemoryItem",
    "is_eligible_for_semantic_promotion",
    "similarity_score",
    "EventType",
    "EventStatus",
    "ExecutiveEvent",
    "EVENT_SCHEMA_VERSION",
    "MAX_EVENT_ATTEMPTS",
    "is_stale_event",
    "is_future_dated",
]
