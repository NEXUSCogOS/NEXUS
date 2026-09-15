"""NEXUS F9 Phase B: Mission Lifecycle Persistence.

Tests persistent mission state through canonical FederationStore.

Critical test: RESTART_RECOVERY_STATUS (decisive for entire F9 architecture).
Missions must survive process restart with state preserved.
"""

import pytest
import tempfile
from pathlib import Path

from executive import ExecutiveCoordinator
from executive.mission_state import MissionState, validate_transition, is_terminal
from persistence.db import FederationStore


class TestMissionStateVocabulary:
    """Test the mission state machine definition."""

    def test_all_states_defined(self):
        """All required states are in the enum."""
        required = {
            "PROPOSED", "VALIDATED", "QUEUED", "CLAIMED", "RUNNING",
            "WAITING_DEPENDENCY", "DEGRADED", "COMPLETED", "FAILED",
            "RETRYABLE", "REJECTED", "EXPIRED", "CANCELLED", "SUPERSEDED",
        }
        defined = {s.value for s in MissionState}
        assert required == defined

    def test_terminal_states_identified(self):
        """Terminal states are correctly identified."""
        terminal = {MissionState.COMPLETED, MissionState.REJECTED, MissionState.EXPIRED,
                   MissionState.CANCELLED, MissionState.SUPERSEDED}
        for state in MissionState:
            if state in terminal:
                assert is_terminal(state), f"{state} should be terminal"
            else:
                assert not is_terminal(state), f"{state} should not be terminal"


class TestMissionStateTransitions:
    """Test state machine transition rules."""

    def test_legal_transition_proposed_to_validated(self):
        """PROPOSED → VALIDATED is legal."""
        valid, reason = validate_transition(None, MissionState.PROPOSED)
        assert valid

        valid, reason = validate_transition(MissionState.PROPOSED, MissionState.VALIDATED)
        assert valid

    def test_illegal_transition_proposed_to_completed(self):
        """PROPOSED → COMPLETED is illegal (skip intermediate states)."""
        valid, reason = validate_transition(MissionState.PROPOSED, MissionState.COMPLETED)
        assert not valid
        assert "invalid" in reason.lower()

    def test_legal_transition_happy_path(self):
        """Full happy path: PROPOSED → VALIDATED → QUEUED → CLAIMED → RUNNING → COMPLETED."""
        path = [
            (None, MissionState.PROPOSED),
            (MissionState.PROPOSED, MissionState.VALIDATED),
            (MissionState.VALIDATED, MissionState.QUEUED),
            (MissionState.QUEUED, MissionState.CLAIMED),
            (MissionState.CLAIMED, MissionState.RUNNING),
            (MissionState.RUNNING, MissionState.COMPLETED),
        ]
        for from_state, to_state in path:
            valid, reason = validate_transition(from_state, to_state)
            assert valid, f"transition {from_state} → {to_state} should be valid: {reason}"

    def test_legal_transition_failure_retry_path(self):
        """Failure path: RUNNING → FAILED → RETRYABLE → QUEUED."""
        path = [
            (MissionState.RUNNING, MissionState.FAILED),
            (MissionState.FAILED, MissionState.RETRYABLE),
            (MissionState.RETRYABLE, MissionState.QUEUED),
        ]
        for from_state, to_state in path:
            valid, reason = validate_transition(from_state, to_state)
            assert valid, f"failure path {from_state} → {to_state} should be valid"

    def test_terminal_state_no_transitions(self):
        """Terminal states cannot transition anywhere."""
        terminal_states = [
            MissionState.COMPLETED, MissionState.REJECTED, MissionState.EXPIRED,
            MissionState.CANCELLED, MissionState.SUPERSEDED,
        ]
        for terminal in terminal_states:
            # Try to transition to any non-terminal state
            for target in [MissionState.RUNNING, MissionState.QUEUED]:
                valid, reason = validate_transition(terminal, target)
                assert not valid, f"{terminal} should not transition to {target}"


class TestMissionLifecyclePersistence:
    """Test mission lifecycle persistence in FederationStore."""

    def test_record_and_retrieve_transition(self, temp_store):
        """Record a transition and retrieve current state."""
        delegation_id = "delg_test_1"
        coordinator = ExecutiveCoordinator(temp_store)

        # Propose mission
        success, reason = coordinator.transition_mission(
            delegation_id,
            MissionState.PROPOSED,
            "mission created",
        )
        assert success, f"transition failed: {reason}"

        # Verify state persisted
        state = coordinator.get_mission_state(delegation_id)
        assert state == "PROPOSED"

    def test_state_history_preserved(self, temp_store):
        """Full transition history is preserved."""
        delegation_id = "delg_history_test"
        coordinator = ExecutiveCoordinator(temp_store)

        # Execute path: PROPOSED → VALIDATED → QUEUED
        for to_state in [MissionState.PROPOSED, MissionState.VALIDATED, MissionState.QUEUED]:
            success, reason = coordinator.transition_mission(
                delegation_id,
                to_state,
                f"transitioning to {to_state.value}",
            )
            assert success

        # Retrieve history
        history = coordinator.get_mission_history(delegation_id)
        assert len(history) == 3
        states = [event["new_state"] for event in history]
        assert states == ["QUEUED", "VALIDATED", "PROPOSED"]  # newest first

    def test_illegal_transition_rejected(self, temp_store):
        """Illegal transitions are rejected with no state change."""
        delegation_id = "delg_illegal_test"
        coordinator = ExecutiveCoordinator(temp_store)

        # Propose
        coordinator.transition_mission(delegation_id, MissionState.PROPOSED, "initial")

        # Try illegal: PROPOSED → COMPLETED
        success, reason = coordinator.transition_mission(
            delegation_id,
            MissionState.COMPLETED,
            "illegal jump",
        )
        assert not success
        assert "invalid" in reason.lower()

        # Verify state unchanged
        state = coordinator.get_mission_state(delegation_id)
        assert state == "PROPOSED"


class TestMissionRestartRecovery:
    """DECISIVE TEST: Mission state survives process restart.

    This test is the critical proof that F9 architecture is sound.
    If it fails, the entire composition model is unacceptable.
    """

    def test_restart_recovery_process_a_to_b(self):
        """Process A creates mission, Process B recovers it (simulated).

        Simulates:
        - Process A: create mission, persist PROPOSED → VALIDATED → QUEUED
        - Restart (clean new Python interpreter state)
        - Process B: new coordinator, same store, recover mission state
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "federation.db"

            # PROCESS A: Create and advance mission
            store_a = FederationStore(db_path)
            coordinator_a = ExecutiveCoordinator(store_a)

            delegation_id = "delg_restart_test"
            for state in [MissionState.PROPOSED, MissionState.VALIDATED, MissionState.QUEUED]:
                success, _ = coordinator_a.transition_mission(
                    delegation_id,
                    state,
                    f"process_a: advancing to {state.value}",
                )
                assert success

            # Verify Process A's final state
            state_a = coordinator_a.get_mission_state(delegation_id)
            assert state_a == "QUEUED"
            history_a = coordinator_a.get_mission_history(delegation_id)
            assert len(history_a) == 3

            # PROCESS B (simulated restart): New coordinator, same database
            store_b = FederationStore(db_path)
            coordinator_b = ExecutiveCoordinator(store_b)

            # Recover mission state from same store
            state_b = coordinator_b.get_mission_state(delegation_id)
            assert state_b == "QUEUED", "state must survive restart"

            history_b = coordinator_b.get_mission_history(delegation_id)
            assert len(history_b) == 3, "history must survive restart"

            # Advance further in Process B
            success, _ = coordinator_b.transition_mission(
                delegation_id,
                MissionState.CLAIMED,
                "process_b: claiming",
            )
            assert success

            state_b_after = coordinator_b.get_mission_state(delegation_id)
            assert state_b_after == "CLAIMED"

            # PROCESS C (another restart): Verify accumulated state
            store_c = FederationStore(db_path)
            coordinator_c = ExecutiveCoordinator(store_c)

            state_c = coordinator_c.get_mission_state(delegation_id)
            assert state_c == "CLAIMED", "state from Process B must persist"

            history_c = coordinator_c.get_mission_history(delegation_id)
            assert len(history_c) == 4, "all 4 transitions must be in history"

    def test_restart_recovery_no_duplicate_action(self):
        """Replaying the same transition doesn't create duplicate state changes.

        CORRECTED (F9 Phase I pre-existing-failure repair): the original
        version of this test asserted BOTH success AND a second history
        entry for a replayed PROPOSED transition -- but PROPOSED->PROPOSED
        is a self-loop, illegal under the Phase B state machine (see
        mission_state.LEGAL_TRANSITIONS; validate_transition correctly
        rejects it via can_transition returning False for any from_state
        not explicitly listing itself as a legal target). Accepting it and
        logging a second event would BE the duplicate state change the
        docstring says must not happen -- the original assertions
        contradicted the test's own stated intent.

        The state machine's rejection of the illegal replay IS the correct
        "no duplicate state change" behavior: the mission remains in
        PROPOSED, with exactly one lifecycle event, regardless of how many
        times an identical PROPOSED transition is (illegitimately) replayed.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "federation.db"

            store = FederationStore(db_path)
            coordinator = ExecutiveCoordinator(store)
            delegation_id = "delg_idempotency_test"

            # First transition
            success1, _ = coordinator.transition_mission(
                delegation_id,
                MissionState.PROPOSED,
                "first attempt",
            )
            assert success1

            # Replay: identical transition request -- correctly rejected as
            # an illegal self-loop, not accepted as a second state change.
            success2, reason2 = coordinator.transition_mission(
                delegation_id,
                MissionState.PROPOSED,
                "second attempt (replay)",
            )
            assert success2 is False
            assert "invalid transition" in reason2

            # Exactly one state change occurred -- no duplicate.
            history = coordinator.get_mission_history(delegation_id)
            assert len(history) == 1
            assert coordinator.get_mission_state(delegation_id) == "PROPOSED"

            # But current state is still PROPOSED (no "double PROPOSED")
            state = coordinator.get_mission_state(delegation_id)
            assert state == "PROPOSED"


class TestListMissionsByState:
    """Test querying missions by current state."""

    def test_list_missions_by_state(self, temp_store):
        """Can query missions in a specific state."""
        coordinator = ExecutiveCoordinator(temp_store)

        # Create 3 missions in different states
        missions = [
            ("delg_queued_1", MissionState.QUEUED),
            ("delg_queued_2", MissionState.QUEUED),
            ("delg_running_1", MissionState.RUNNING),
        ]

        for delg_id, state in missions:
            # First PROPOSED, then target state
            coordinator.transition_mission(delg_id, MissionState.PROPOSED, "init")
            if state != MissionState.PROPOSED:
                coordinator.transition_mission(delg_id, MissionState.VALIDATED, "validate")
            if state != MissionState.VALIDATED:
                coordinator.transition_mission(delg_id, state, f"advance to {state.value}")

        # Query missions in QUEUED state
        queued = coordinator.list_missions_by_state("QUEUED")
        assert len(queued) == 2
        assert set(queued) == {"delg_queued_1", "delg_queued_2"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
