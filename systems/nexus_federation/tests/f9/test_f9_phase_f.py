"""NEXUS F9 Phase F: Retry / Timeout / Leases / Circuit Breakers.

Mandatory: restart recovery test.
"""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from executive import (
    ExecutiveCoordinator,
    MissionState,
    RetryDecision,
    RetryPolicy,
    decide_retry,
    is_lease_expired,
    is_mission_timed_out,
    CircuitState,
    CircuitBreakerPolicy,
    next_circuit_state,
)
from persistence.db import FederationStore


# === RETRY DECISION TESTS ===

def test_retry_transient_failure():
    """Transient failure classes are retryable up to max_attempts."""
    decision, reason = decide_retry(retry_count=0, failure_class="TRANSIENT_DEPENDENCY_FAILURE")
    assert decision == RetryDecision.RETRY


def test_retry_non_retryable_failure():
    """Non-retryable failure classes never retry."""
    decision, reason = decide_retry(retry_count=0, failure_class="AUTHORITY_REJECTION")
    assert decision == RetryDecision.NO_RETRY_NON_RETRYABLE_FAILURE


def test_retry_max_attempts_exceeded():
    """Retry stops once max_attempts reached, even for transient failures."""
    policy = RetryPolicy(max_attempts=3)
    decision, reason = decide_retry(retry_count=3, failure_class="TIMEOUT", policy=policy)
    assert decision == RetryDecision.NO_RETRY_MAX_ATTEMPTS_EXCEEDED


def test_retry_backoff_exponential():
    """Backoff increases exponentially, capped at max."""
    policy = RetryPolicy(base_backoff_seconds=5.0, backoff_multiplier=2.0, max_backoff_seconds=60.0)
    assert policy.backoff_for_attempt(1) == 5.0
    assert policy.backoff_for_attempt(2) == 10.0
    assert policy.backoff_for_attempt(3) == 20.0
    assert policy.backoff_for_attempt(10) == 60.0  # capped


def test_retry_unknown_failure_class_conservative():
    """Unrecognized failure classes default to no-retry (conservative)."""
    decision, reason = decide_retry(retry_count=0, failure_class="SOME_UNKNOWN_CLASS")
    assert decision == RetryDecision.NO_RETRY_NON_RETRYABLE_FAILURE


# === LEASE EXPIRY TESTS ===

def test_lease_not_expired():
    """Fresh lease is not expired."""
    now = datetime.now(timezone.utc)
    acquired_at = now.isoformat()
    assert not is_lease_expired(acquired_at, ttl_seconds=60.0, now=now)


def test_lease_expired():
    """Lease past TTL is expired."""
    now = datetime.now(timezone.utc)
    acquired_at = (now - timedelta(seconds=120)).isoformat()
    assert is_lease_expired(acquired_at, ttl_seconds=60.0, now=now)


def test_lease_expiry_via_coordinator():
    """Coordinator detects expired lease from persisted lifecycle history."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "federation.db"
        store = FederationStore(db_path)
        coordinator = ExecutiveCoordinator(store)

        delegation_id = "delg_lease_test"
        coordinator.transition_mission(delegation_id, MissionState.PROPOSED, "start")
        coordinator.transition_mission(delegation_id, MissionState.VALIDATED, "validated")
        coordinator.transition_mission(delegation_id, MissionState.QUEUED, "queued")
        coordinator.transition_mission(
            delegation_id, MissionState.CLAIMED, "claimed", lease_id="lease_001"
        )

        # Immediately check: lease should not be expired with generous TTL
        assert not coordinator.check_lease_expired(delegation_id, ttl_seconds=3600.0)

        # With TTL of 0, it's immediately expired
        assert coordinator.check_lease_expired(
            delegation_id, ttl_seconds=0.0, now=datetime.now(timezone.utc) + timedelta(seconds=1)
        )


# === TIMEOUT TESTS ===

def test_mission_not_timed_out():
    """Running mission within timeout window is not timed out."""
    now = datetime.now(timezone.utc)
    started_at = now.isoformat()
    assert not is_mission_timed_out(started_at, timeout_seconds=300.0, now=now)


def test_mission_timed_out():
    """Running mission past timeout window is timed out."""
    now = datetime.now(timezone.utc)
    started_at = (now - timedelta(seconds=600)).isoformat()
    assert is_mission_timed_out(started_at, timeout_seconds=300.0, now=now)


def test_mission_timeout_via_coordinator():
    """Coordinator detects mission timeout from RUNNING transition timestamp."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "federation.db"
        store = FederationStore(db_path)
        coordinator = ExecutiveCoordinator(store)

        delegation_id = "delg_timeout_test"
        coordinator.transition_mission(delegation_id, MissionState.PROPOSED, "start")
        coordinator.transition_mission(delegation_id, MissionState.VALIDATED, "validated")
        coordinator.transition_mission(delegation_id, MissionState.QUEUED, "queued")
        coordinator.transition_mission(delegation_id, MissionState.CLAIMED, "claimed")
        coordinator.transition_mission(delegation_id, MissionState.RUNNING, "running")

        assert not coordinator.check_mission_timeout(delegation_id, timeout_seconds=3600.0)
        assert coordinator.check_mission_timeout(
            delegation_id, timeout_seconds=0.0, now=datetime.now(timezone.utc) + timedelta(seconds=1)
        )


# === CIRCUIT BREAKER TRANSITION TESTS ===

def test_circuit_closed_stays_closed_below_threshold():
    """CLOSED stays CLOSED while failures below threshold."""
    policy = CircuitBreakerPolicy(failure_threshold=5)
    state, reason = next_circuit_state(
        current_state="CLOSED",
        consecutive_failures=3,
        consecutive_successes=0,
        policy=policy,
    )
    assert state == CircuitState.CLOSED


def test_circuit_closed_to_open():
    """CLOSED -> OPEN when failure threshold reached."""
    policy = CircuitBreakerPolicy(failure_threshold=5)
    state, reason = next_circuit_state(
        current_state="CLOSED",
        consecutive_failures=5,
        consecutive_successes=0,
        policy=policy,
    )
    assert state == CircuitState.OPEN


def test_circuit_open_to_half_open_after_cooldown():
    """OPEN -> HALF_OPEN after cooldown elapses."""
    policy = CircuitBreakerPolicy(half_open_after_seconds=60.0)
    now = datetime.now(timezone.utc)
    opened_at = (now - timedelta(seconds=120)).isoformat()

    state, reason = next_circuit_state(
        current_state="OPEN",
        consecutive_failures=0,
        consecutive_successes=0,
        opened_at_iso=opened_at,
        policy=policy,
        now=now,
    )
    assert state == CircuitState.HALF_OPEN


def test_circuit_open_stays_open_within_cooldown():
    """OPEN stays OPEN while cooldown has not elapsed."""
    policy = CircuitBreakerPolicy(half_open_after_seconds=60.0)
    now = datetime.now(timezone.utc)
    opened_at = (now - timedelta(seconds=10)).isoformat()

    state, reason = next_circuit_state(
        current_state="OPEN",
        consecutive_failures=0,
        consecutive_successes=0,
        opened_at_iso=opened_at,
        policy=policy,
        now=now,
    )
    assert state == CircuitState.OPEN


def test_circuit_half_open_to_closed_on_trial_success():
    """HALF_OPEN -> CLOSED once trial successes met."""
    policy = CircuitBreakerPolicy(half_open_trial_successes_required=2)
    state, reason = next_circuit_state(
        current_state="HALF_OPEN",
        consecutive_failures=0,
        consecutive_successes=2,
        policy=policy,
    )
    assert state == CircuitState.CLOSED


def test_circuit_half_open_reopens_on_failure():
    """HALF_OPEN -> OPEN immediately on any failure during trial."""
    state, reason = next_circuit_state(
        current_state="HALF_OPEN",
        consecutive_failures=1,
        consecutive_successes=0,
    )
    assert state == CircuitState.OPEN


def test_circuit_breaker_via_coordinator():
    """Coordinator advances circuit breaker and persists via institution_capacity."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "federation.db"
        store = FederationStore(db_path)
        coordinator = ExecutiveCoordinator(store)

        coordinator.update_institution_capacity(
            "sentinel", {"circuit_state": "CLOSED", "availability_state": "AVAILABLE"}
        )

        new_state, reason = coordinator.advance_circuit_breaker(
            "sentinel", consecutive_failures=5, consecutive_successes=0
        )
        assert new_state == "OPEN"

        capacity = coordinator.get_institution_capacity("sentinel")
        assert capacity["circuit_state"] == "OPEN"


# === MANDATORY RESTART RECOVERY ===

def test_phase_f_restart_recovery():
    """MANDATORY: Retry/lease/circuit state survives process restarts.

    Process A: Claim mission with lease, trip circuit breaker to OPEN.
    Process B: Recover lease state and circuit state; verify expiry detection.
    Process C: Re-verify persistence.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "federation.db"

        # PROCESS A
        store_a = FederationStore(db_path)
        coordinator_a = ExecutiveCoordinator(store_a)

        delegation_id = "delg_restart_f"
        coordinator_a.transition_mission(delegation_id, MissionState.PROPOSED, "start")
        coordinator_a.transition_mission(delegation_id, MissionState.VALIDATED, "validated")
        coordinator_a.transition_mission(delegation_id, MissionState.QUEUED, "queued")
        coordinator_a.transition_mission(
            delegation_id, MissionState.CLAIMED, "claimed", lease_id="lease_restart_1"
        )

        coordinator_a.update_institution_capacity(
            "news_intel", {"circuit_state": "CLOSED", "availability_state": "AVAILABLE"}
        )
        coordinator_a.advance_circuit_breaker("news_intel", consecutive_failures=5, consecutive_successes=0)

        # PROCESS B (restart)
        store_b = FederationStore(db_path)
        coordinator_b = ExecutiveCoordinator(store_b)

        # Verify lease state recovered
        history = coordinator_b.get_mission_history(delegation_id)
        assert history[0]["lease_id"] == "lease_restart_1"
        assert not coordinator_b.check_lease_expired(delegation_id, ttl_seconds=3600.0)

        # Verify circuit breaker state recovered
        capacity_b = coordinator_b.get_institution_capacity("news_intel")
        assert capacity_b["circuit_state"] == "OPEN"

        # PROCESS C (another restart)
        store_c = FederationStore(db_path)
        coordinator_c = ExecutiveCoordinator(store_c)

        capacity_c = coordinator_c.get_institution_capacity("news_intel")
        assert capacity_c["circuit_state"] == "OPEN"
        history_c = coordinator_c.get_mission_history(delegation_id)
        assert history_c[0]["lease_id"] == "lease_restart_1"

        print("✓✓✓ RESTART_RECOVERY_STATUS = PASS")
        print("Lease and circuit breaker state survived process restarts.")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
