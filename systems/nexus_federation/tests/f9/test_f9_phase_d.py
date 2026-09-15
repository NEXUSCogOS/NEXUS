"""NEXUS F9 Phase D: Institution Capacity.

Mandatory: restart recovery test.
"""

import tempfile
from pathlib import Path

from executive import ExecutiveCoordinator, AvailabilityState, CircuitState
from persistence.db import FederationStore


def test_phase_d_restart_recovery():
    """MANDATORY: Capacity state survives restarts.

    Process A: Set capacity, run mission.
    Process B: Recover capacity, verify active counts.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "federation.db"

        # PROCESS A: Set capacity
        store_a = FederationStore(db_path)
        coordinator_a = ExecutiveCoordinator(store_a)

        capacity_a = {
            "availability_state": AvailabilityState.AVAILABLE.value,
            "max_concurrent_missions": 2,
            "active_missions": 1,
            "queued_missions": 1,
            "circuit_state": CircuitState.CLOSED.value,
        }
        coordinator_a.update_institution_capacity("sentinel", capacity_a)

        # Verify set
        cap_a = coordinator_a.get_institution_capacity("sentinel")
        assert cap_a is not None
        assert cap_a["active_missions"] == 1
        assert cap_a["availability_state"] == AvailabilityState.AVAILABLE.value

        # PROCESS B (restart): Recover
        store_b = FederationStore(db_path)
        coordinator_b = ExecutiveCoordinator(store_b)

        cap_b = coordinator_b.get_institution_capacity("sentinel")
        assert cap_b is not None
        assert cap_b["active_missions"] == 1, "active_missions must survive restart"
        assert cap_b["queued_missions"] == 1, "queued_missions must survive restart"
        assert cap_b["availability_state"] == AvailabilityState.AVAILABLE.value

        # PROCESS C (another restart): Verify persistence
        store_c = FederationStore(db_path)
        coordinator_c = ExecutiveCoordinator(store_c)

        cap_c = coordinator_c.get_institution_capacity("sentinel")
        assert cap_c is not None
        assert cap_c["active_missions"] == 1
        assert cap_c["circuit_state"] == CircuitState.CLOSED.value

        print("✓✓✓ RESTART_RECOVERY_STATUS = PASS")
        print("Capacity state survived all process restarts.")


if __name__ == "__main__":
    test_phase_d_restart_recovery()
