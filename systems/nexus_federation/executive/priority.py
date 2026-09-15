"""NEXUS Executive Priority Model.

F9 hardening: separate PRIORITY from ATTENTION.

Attention: "Is this interesting and important?" (factor-based scoring)
Priority: "When should we act on it?" (deadline, dependency, risk, cost)

Explicit priority classes. Basis always recorded.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class PriorityClass(str, Enum):
    CRITICAL = "CRITICAL"  # Act immediately; blocks other work
    HIGH = "HIGH"  # Next available slot
    NORMAL = "NORMAL"  # Standard queue order
    LOW = "LOW"  # After normal/high; deferred OK
    DEFERRED = "DEFERRED"  # Explicitly postponed; revisit later


@dataclass(frozen=True)
class PriorityFactors:
    """Explicit factors informing priority decision.

    Separate from attention: same finding can be high-attention (interesting)
    but low-priority (can wait).
    """

    deadline_urgency: float  # 0.0 (no deadline) to 1.0 (imminent, hours)
    dependency_blocking: float  # 0.0 (no blocker) to 1.0 (multiple missions waiting)
    information_gain: float  # 0.0 (routine) to 1.0 (fundamentally new knowledge)
    cost_to_act: float  # 0.0 (free) to 1.0 (expensive) -- INVERTED in scoring
    resource_contention: float  # 0.0 (free resources) to 1.0 (all resources occupied)
    mission_criticality: float  # 0.0 (optional) to 1.0 (existential importance)
    reversibility: float  # 0.0 (permanent) to 1.0 (fully reversible)

    def __post_init__(self):
        for name, value in self.__dict__.items():
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{name} must be in [0.0, 1.0], got {value}")


def compute_priority_score(
    factors: PriorityFactors,
    now: datetime | None = None,
) -> float:
    """Deterministic priority scoring.

    Returns float [0.0, 1.0], higher = more urgent.

    Logic:
    - Imminent deadlines push priority up
    - Blocking other missions pushes priority up
    - High cost suppresses priority (defer if possible)
    - Reversible work can be deferred; irreversible is more urgent
    """
    now = now or datetime.now(timezone.utc)

    # Deadlines are hard: imminent deadlines boost priority. Coefficient
    # raised from 0.35 to 0.45 (F9 Phase I pre-existing-defect repair,
    # commit-referenced): at the old coefficient, max deadline_urgency=1.0
    # alone -- even combined with modest learning/cost/reversibility
    # contributions from a genuinely urgent, non-blocking mission -- could
    # not cross the HIGH threshold (0.6). A deadline that is "hours away"
    # (deadline_urgency=1.0) must be able to independently drive priority
    # into HIGH/CRITICAL; it should not require an additional blocking or
    # high-cost factor to get there. No other module reads these
    # coefficients (verified: priority.py is their only consumer), and the
    # DEFERRED-classification test is unaffected since it exercises
    # deadline_urgency=0.0.
    deadline_weight = factors.deadline_urgency * 0.45

    # Dependencies matter: if this blocks other work, do it first.
    # Coefficient raised from 0.25 to 0.35 for the same reason: blocking
    # multiple other missions (dependency_blocking=1.0) must be able to
    # independently reach HIGH priority.
    blocker_weight = factors.dependency_blocking * 0.35

    # Information gain: learning something fundamental is worth the cost.
    learning_weight = factors.information_gain * 0.15

    # Cost suppresses priority: expensive work is deferred if deadline isn't urgent.
    cost_penalty = (1.0 - factors.cost_to_act) * 0.15

    # Reversible work can wait; irreversible is more urgent.
    reversibility_weight = (1.0 - factors.reversibility) * factors.mission_criticality * 0.1

    # If all resources are taken, defer non-critical work.
    if factors.resource_contention > 0.8 and factors.mission_criticality < 0.5:
        return 0.1  # Very low priority

    score = (
        deadline_weight +
        blocker_weight +
        learning_weight +
        cost_penalty +
        reversibility_weight
    )

    return min(1.0, max(0.0, score))


def classify_priority(score: float) -> PriorityClass:
    """Map numeric score to priority class."""
    if score >= 0.8:
        return PriorityClass.CRITICAL
    elif score >= 0.6:
        return PriorityClass.HIGH
    elif score >= 0.4:
        return PriorityClass.NORMAL
    elif score >= 0.2:
        return PriorityClass.LOW
    else:
        return PriorityClass.DEFERRED


@dataclass(frozen=True)
class PriorityDecision:
    """A priority assignment with explicit basis."""

    mission_id: str
    priority_class: PriorityClass
    priority_score: float
    factors: PriorityFactors
    basis: str  # why this priority (free text, not parsed)
    decided_at: str  # ISO 8601

    @classmethod
    def from_factors(
        cls,
        mission_id: str,
        factors: PriorityFactors,
        basis: str,
        now: datetime | None = None,
    ) -> "PriorityDecision":
        score = compute_priority_score(factors, now=now)
        priority_class = classify_priority(score)
        decided_at = (now or datetime.now(timezone.utc)).isoformat()
        return cls(
            mission_id=mission_id,
            priority_class=priority_class,
            priority_score=score,
            factors=factors,
            basis=basis,
            decided_at=decided_at,
        )
