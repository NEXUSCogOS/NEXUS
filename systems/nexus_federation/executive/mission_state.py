"""F9 Mission Lifecycle State Machine.

Canonical state vocabulary and transition rules.

States are NOT arbitrary strings; they come from an explicit vocabulary.
Transitions follow explicit rules; illegal transitions are rejected.

This module is independent of persistence; it validates the rules.
Persistence happens in FederationStore via record_mission_transition().
"""

from enum import Enum
from typing import Optional


class MissionState(str, Enum):
    """Canonical mission lifecycle states."""

    PROPOSED = "PROPOSED"  # Initial, schema validated
    VALIDATED = "VALIDATED"  # Ready for scheduling
    QUEUED = "QUEUED"  # Waiting for availability
    CLAIMED = "CLAIMED"  # Institution accepted, will execute
    RUNNING = "RUNNING"  # Active execution
    WAITING_DEPENDENCY = "WAITING_DEPENDENCY"  # Blocked on upstream mission
    DEGRADED = "DEGRADED"  # Running, but in reduced capacity mode
    COMPLETED = "COMPLETED"  # Success
    FAILED = "FAILED"  # Execution failed
    RETRYABLE = "RETRYABLE"  # Failed, eligible for retry
    REJECTED = "REJECTED"  # Refused (policy, validation, etc)
    EXPIRED = "EXPIRED"  # Deadline passed
    CANCELLED = "CANCELLED"  # Explicitly cancelled
    SUPERSEDED = "SUPERSEDED"  # Replaced by newer mission


# Explicit legal transition rules
# Maps (from_state -> set of allowed_to_states)
LEGAL_TRANSITIONS = {
    MissionState.PROPOSED: {
        MissionState.VALIDATED,
        MissionState.REJECTED,
        MissionState.CANCELLED,
    },
    MissionState.VALIDATED: {
        MissionState.QUEUED,
        MissionState.REJECTED,
        MissionState.CANCELLED,
    },
    MissionState.QUEUED: {
        MissionState.CLAIMED,
        MissionState.EXPIRED,
        MissionState.CANCELLED,
        MissionState.SUPERSEDED,
    },
    MissionState.CLAIMED: {
        MissionState.RUNNING,
        MissionState.WAITING_DEPENDENCY,
        MissionState.REJECTED,
        MissionState.CANCELLED,
        MissionState.SUPERSEDED,
    },
    MissionState.RUNNING: {
        MissionState.COMPLETED,
        MissionState.FAILED,
        MissionState.DEGRADED,
        MissionState.WAITING_DEPENDENCY,
        MissionState.CANCELLED,
        MissionState.SUPERSEDED,
    },
    MissionState.DEGRADED: {
        MissionState.RUNNING,
        MissionState.COMPLETED,
        MissionState.FAILED,
        MissionState.CANCELLED,
        MissionState.SUPERSEDED,
    },
    MissionState.WAITING_DEPENDENCY: {
        MissionState.QUEUED,
        MissionState.EXPIRED,
        MissionState.CANCELLED,
        MissionState.SUPERSEDED,
    },
    MissionState.FAILED: {
        MissionState.RETRYABLE,
        MissionState.CANCELLED,
        MissionState.SUPERSEDED,
    },
    MissionState.RETRYABLE: {
        MissionState.QUEUED,
        MissionState.CANCELLED,
        MissionState.SUPERSEDED,
    },
    MissionState.COMPLETED: set(),  # Terminal: no transitions
    MissionState.REJECTED: set(),  # Terminal: no transitions
    MissionState.EXPIRED: set(),  # Terminal: no transitions
    MissionState.CANCELLED: set(),  # Terminal: no transitions
    MissionState.SUPERSEDED: set(),  # Terminal: no transitions
}


def is_terminal(state: MissionState) -> bool:
    """True if state is terminal (no further transitions possible)."""
    return len(LEGAL_TRANSITIONS.get(state, set())) == 0


def can_transition(from_state: MissionState, to_state: MissionState) -> bool:
    """True if transition from_state -> to_state is legal."""
    allowed = LEGAL_TRANSITIONS.get(from_state, set())
    return to_state in allowed


def validate_transition(
    from_state: Optional[MissionState],
    to_state: MissionState,
) -> tuple[bool, str]:
    """Validate a state transition.

    Returns (valid, reason).
    """
    if from_state is None:
        # Initial PROPOSED transition (no prior state)
        if to_state == MissionState.PROPOSED:
            return True, "valid initial state"
        else:
            return False, f"cannot start in state {to_state}; must be PROPOSED"

    if not can_transition(from_state, to_state):
        allowed = LEGAL_TRANSITIONS.get(from_state, set())
        return False, f"invalid transition {from_state} → {to_state}; allowed: {allowed}"

    return True, "valid transition"
