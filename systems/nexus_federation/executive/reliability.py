"""F9 Phase F: Retry / Timeout / Leases / Circuit Breakers.

Deterministic reliability policy for mission execution.
No hidden retries: every retry decision is explicit, bounded, and logged
through the canonical mission_lifecycle_event trail (Phase B).

Circuit breaker state extends the existing institution_capacity model
(Phase D) rather than duplicating it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from executive.capacity import CircuitState


class RetryDecision(str, Enum):
    """Deterministic retry classification."""
    RETRY = "RETRY"
    NO_RETRY_TERMINAL_SUCCESS = "NO_RETRY_TERMINAL_SUCCESS"
    NO_RETRY_MAX_ATTEMPTS_EXCEEDED = "NO_RETRY_MAX_ATTEMPTS_EXCEEDED"
    NO_RETRY_NON_RETRYABLE_FAILURE = "NO_RETRY_NON_RETRYABLE_FAILURE"
    NO_RETRY_LEASE_STILL_VALID = "NO_RETRY_LEASE_STILL_VALID"


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded, explicit retry policy. No silent unbounded retries."""
    max_attempts: int = 3
    base_backoff_seconds: float = 5.0
    backoff_multiplier: float = 2.0
    max_backoff_seconds: float = 300.0

    def backoff_for_attempt(self, attempt: int) -> float:
        """Exponential backoff, capped at max_backoff_seconds."""
        delay = self.base_backoff_seconds * (self.backoff_multiplier ** max(0, attempt - 1))
        return min(delay, self.max_backoff_seconds)


DEFAULT_RETRY_POLICY = RetryPolicy()

# Failure classes eligible for retry (transient) vs. not (persistent/structural).
RETRYABLE_FAILURE_CLASSES = frozenset({
    "TRANSIENT_DEPENDENCY_FAILURE",
    "TIMEOUT",
    "INSTITUTION_UNAVAILABLE",
    "RESOURCE_EXHAUSTION",
})

NON_RETRYABLE_FAILURE_CLASSES = frozenset({
    "PERSISTENT_DEPENDENCY_FAILURE",
    "INVALID_INPUT",
    "POLICY_REJECTION",
    "AUTHORITY_REJECTION",
    "INTERNAL_DEFECT",
})


def decide_retry(
    *,
    retry_count: int,
    failure_class: Optional[str],
    policy: RetryPolicy = DEFAULT_RETRY_POLICY,
) -> tuple[RetryDecision, str]:
    """Deterministic retry decision. Returns (decision, reason)."""
    if retry_count >= policy.max_attempts:
        return (
            RetryDecision.NO_RETRY_MAX_ATTEMPTS_EXCEEDED,
            f"retry_count {retry_count} >= max_attempts {policy.max_attempts}",
        )

    if failure_class in NON_RETRYABLE_FAILURE_CLASSES:
        return (
            RetryDecision.NO_RETRY_NON_RETRYABLE_FAILURE,
            f"failure_class {failure_class} is not retryable",
        )

    if failure_class in RETRYABLE_FAILURE_CLASSES:
        return (
            RetryDecision.RETRY,
            f"failure_class {failure_class} is retryable, attempt {retry_count + 1}/{policy.max_attempts}",
        )

    # Unknown failure class: conservative default is no retry.
    return (
        RetryDecision.NO_RETRY_NON_RETRYABLE_FAILURE,
        f"failure_class {failure_class} unrecognized -- conservative no-retry",
    )


# ---- Leases ----

@dataclass(frozen=True)
class Lease:
    """A time-bounded claim on a mission by an executor.

    Leases prevent duplicate concurrent execution. A lease has a fixed
    expiry; if the holder doesn't renew or complete before expiry, the
    mission becomes claimable again (RETRYABLE).
    """
    lease_id: str
    delegation_id: str
    holder: str
    acquired_at: datetime
    ttl_seconds: float

    @property
    def expires_at(self) -> datetime:
        return self.acquired_at + timedelta(seconds=self.ttl_seconds)

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return now >= self.expires_at


def is_lease_expired(acquired_at_iso: str, ttl_seconds: float, now: Optional[datetime] = None) -> bool:
    """Check lease expiry from persisted ISO timestamp (restart-safe)."""
    now = now or datetime.now(timezone.utc)
    acquired_at = datetime.fromisoformat(acquired_at_iso)
    if acquired_at.tzinfo is None:
        acquired_at = acquired_at.replace(tzinfo=timezone.utc)
    return now >= acquired_at + timedelta(seconds=ttl_seconds)


# ---- Timeout ----

def is_mission_timed_out(
    started_at_iso: str,
    timeout_seconds: float,
    now: Optional[datetime] = None,
) -> bool:
    """Check whether a RUNNING mission has exceeded its allotted time."""
    now = now or datetime.now(timezone.utc)
    started_at = datetime.fromisoformat(started_at_iso)
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    return now >= started_at + timedelta(seconds=timeout_seconds)


# ---- Circuit Breaker Transitions ----

@dataclass(frozen=True)
class CircuitBreakerPolicy:
    """Explicit circuit breaker thresholds. No implicit tuning."""
    failure_threshold: int = 5
    half_open_after_seconds: float = 60.0
    half_open_trial_successes_required: int = 2


DEFAULT_CIRCUIT_POLICY = CircuitBreakerPolicy()


def next_circuit_state(
    *,
    current_state: str,
    consecutive_failures: int,
    consecutive_successes: int,
    opened_at_iso: Optional[str] = None,
    policy: CircuitBreakerPolicy = DEFAULT_CIRCUIT_POLICY,
    now: Optional[datetime] = None,
) -> tuple[CircuitState, str]:
    """Deterministic circuit breaker state transition.

    CLOSED --(failures >= threshold)--> OPEN
    OPEN --(half_open_after elapsed)--> HALF_OPEN
    HALF_OPEN --(trial successes met)--> CLOSED
    HALF_OPEN --(any failure)--> OPEN
    """
    now = now or datetime.now(timezone.utc)
    current = CircuitState(current_state) if current_state else CircuitState.CLOSED

    if current == CircuitState.CLOSED:
        if consecutive_failures >= policy.failure_threshold:
            return CircuitState.OPEN, f"consecutive_failures {consecutive_failures} >= threshold {policy.failure_threshold}"
        return CircuitState.CLOSED, "within failure threshold"

    if current == CircuitState.OPEN:
        if opened_at_iso:
            opened_at = datetime.fromisoformat(opened_at_iso)
            if opened_at.tzinfo is None:
                opened_at = opened_at.replace(tzinfo=timezone.utc)
            if now >= opened_at + timedelta(seconds=policy.half_open_after_seconds):
                return CircuitState.HALF_OPEN, "half_open_after_seconds elapsed, trial resumption"
        return CircuitState.OPEN, "still within open cooldown"

    if current == CircuitState.HALF_OPEN:
        if consecutive_failures > 0:
            return CircuitState.OPEN, "failure during half-open trial, reopening"
        if consecutive_successes >= policy.half_open_trial_successes_required:
            return CircuitState.CLOSED, f"trial successes {consecutive_successes} met requirement, closing"
        return CircuitState.HALF_OPEN, "trial in progress"

    return CircuitState.CLOSED, "unknown state, defaulting to closed"
