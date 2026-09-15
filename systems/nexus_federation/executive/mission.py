"""NEXUS Executive Mission Lifecycle.

F9 hardening: canonical mission state machine.

Every mission (delegation request, external event, production command)
passes through explicit states. No hidden terminal states.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class MissionState(str, Enum):
    """Canonical mission lifecycle."""

    PROPOSED = "PROPOSED"  # Initial state, schema validated
    VALIDATED = "VALIDATED"  # Attention/priority assessed, dependencies resolved
    QUEUED = "QUEUED"  # Waiting for available resources/institution
    CLAIMED = "CLAIMED"  # Institution has accepted, execution starting
    RUNNING = "RUNNING"  # Active execution
    WAITING_DEPENDENCY = "WAITING_DEPENDENCY"  # Blocked on upstream mission
    DEGRADED = "DEGRADED"  # Running, but in reduced/recovery mode
    COMPLETED = "COMPLETED"  # Execution finished successfully
    FAILED = "FAILED"  # Execution failed, not retryable
    RETRYABLE = "RETRYABLE"  # Execution failed, retry eligible
    REJECTED = "REJECTED"  # Never executed (policy, dependency, etc.)
    EXPIRED = "EXPIRED"  # Deadline passed before execution could start
    CANCELLED = "CANCELLED"  # Explicitly cancelled
    SUPERSEDED = "SUPERSEDED"  # Newer evidence invalidates this mission


@dataclass(frozen=True)
class MissionStateTransition:
    """An auditable state change."""

    mission_id: str
    from_state: MissionState
    to_state: MissionState
    reason: str  # why this transition
    timestamp: str  # ISO 8601
    detail: dict[str, Any] = field(default_factory=dict)  # optional extra data


@dataclass
class ExecutiveMission:
    """A mission owned by the executive kernel.

    Tracks: what we're trying to do, where it is in its lifecycle,
    what resources it's consuming, what its outcome was.
    """

    mission_id: str
    source: str  # DAT.AI event, News trigger, external request, etc.
    objective: str  # what should happen

    # Lifecycle
    current_state: MissionState = MissionState.PROPOSED
    state_transitions: list[MissionStateTransition] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    deadline: Optional[str] = None  # when it must finish (ISO 8601)

    # Execution tracking
    recipient_institution: Optional[str] = None  # which institution is running it
    claimed_by_pid: Optional[int] = None  # which process claimed it
    lease_expires_at: Optional[str] = None  # heartbeat/lease timeout

    # Dependencies
    depends_on: list[str] = field(default_factory=list)  # mission_ids this requires
    blocked_by: list[str] = field(default_factory=list)  # missions currently blocking this
    invalidated_by: list[str] = field(default_factory=list)  # missions that supersede this

    # Resource accounting
    resource_budget: dict[str, Any] = field(default_factory=dict)  # cpu, ram, time, cost, etc.
    resource_used: dict[str, float] = field(default_factory=dict)  # actual consumption

    # Outcome (only populated when COMPLETED/FAILED/REJECTED)
    outcome_class: Optional[str] = None  # SUCCESS/PARTIAL/INSUFFICIENT_EVIDENCE/FAILED/INVALIDATED/NO_ACTION_REQUIRED
    outcome_reason: Optional[str] = None
    outcome_evidence: Optional[dict[str, Any]] = None
    retries_attempted: int = 0

    def transition_to(
        self,
        new_state: MissionState,
        reason: str,
        *,
        detail: Optional[dict[str, Any]] = None,
    ):
        """Record a state transition."""
        now = datetime.now(timezone.utc).isoformat()
        transition = MissionStateTransition(
            mission_id=self.mission_id,
            from_state=self.current_state,
            to_state=new_state,
            reason=reason,
            timestamp=now,
            detail=detail or {},
        )
        self.state_transitions.append(transition)
        self.current_state = new_state

        # Update lifecycle timestamps.
        if new_state == MissionState.RUNNING:
            self.started_at = now
        elif new_state in (MissionState.COMPLETED, MissionState.FAILED, MissionState.REJECTED, MissionState.EXPIRED, MissionState.CANCELLED, MissionState.SUPERSEDED):
            self.completed_at = now

    def is_terminal(self) -> bool:
        """True if the mission is in a terminal state."""
        terminal_states = {
            MissionState.COMPLETED,
            MissionState.FAILED,
            MissionState.REJECTED,
            MissionState.EXPIRED,
            MissionState.CANCELLED,
            MissionState.SUPERSEDED,
        }
        return self.current_state in terminal_states

    def is_active(self) -> bool:
        """True if the mission is currently executing or waiting."""
        active_states = {
            MissionState.RUNNING,
            MissionState.CLAIMED,
            MissionState.WAITING_DEPENDENCY,
            MissionState.DEGRADED,
        }
        return self.current_state in active_states

    def elapsed_seconds(self) -> Optional[float]:
        """Elapsed time from creation to now (or completion)."""
        start = datetime.fromisoformat(self.created_at)
        if self.completed_at:
            end = datetime.fromisoformat(self.completed_at)
        else:
            end = datetime.now(timezone.utc)
        delta = end - start
        return delta.total_seconds()


@dataclass(frozen=True)
class MissionOutcome:
    """Result of a completed mission."""

    mission_id: str
    outcome_class: str  # SUCCESS / PARTIAL_SUCCESS / INSUFFICIENT_EVIDENCE / FAILED / INVALIDATED / NO_ACTION_REQUIRED
    reason: str  # why this outcome
    evidence: dict[str, Any]  # supporting data
    resource_used: dict[str, float]  # actual consumption
    elapsed_seconds: float
    downstream_usefulness: str  # "unknown" / "useful" / "blocked" / "contradictory"
