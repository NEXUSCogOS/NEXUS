"""NEXUS F9 Phase C: Scheduler + Dependencies.

Tests persistent dependency tracking and deterministic mission selection.
"""

import pytest
import tempfile
from pathlib import Path

from executive import ExecutiveCoordinator, MissionState, DependencyType, detect_cycle
from persistence.db import FederationStore


class TestDependencySemantics:
    """Test dependency types and validation."""

    def test_dependency_types_defined(self):
        """All required dependency types exist."""
        required = {"REQUIRES", "OPTIONAL", "BLOCKED_BY", "INVALIDATED_BY", "SUPERSEDES"}
        defined = {dt.value for dt in DependencyType}
        assert required == defined

    def test_cycle_detection_simple(self):
        """Detect direct cycle: A requires B, B requires A."""
        predecessor_map = {"A": ["B"], "B": ["A"]}
        assert detect_cycle("A", predecessor_map) is True

    def test_cycle_detection_indirect(self):
        """Detect indirect cycle: A→B→C→A."""
        predecessor_map = {"A": ["B"], "B": ["C"], "C": ["A"]}
        assert detect_cycle("A", predecessor_map) is True

    def test_no_cycle_simple_chain(self):
        """No cycle in simple chain: A requires B requires C."""
        predecessor_map = {"A": ["B"], "B": ["C"], "C": []}
        assert detect_cycle("A", predecessor_map) is False


class TestSchedulerAndDependencies:
    """Test dependency persistence and scheduler."""

    def test_record_and_retrieve_dependency(self, temp_store):
        """Record dependency and retrieve it."""
        coordinator = ExecutiveCoordinator(temp_store)

        # Create two missions
        for mission_id in ["m_a", "m_b"]:
            success, _ = coordinator.transition_mission(mission_id, MissionState.PROPOSED, "init")
            assert success

        # Record dependency: m_a requires m_b
        success, reason = coordinator.record_dependency(
            "m_a",
            "m_b",
            "REQUIRES",
            "m_a cannot run until m_b completes",
        )
        assert success

        # Retrieve dependencies for m_a
        deps = coordinator.store.get_mission_dependencies("m_a")
        assert len(deps) == 1
        assert deps[0]["dependency_type"] == "REQUIRES"
        assert deps[0]["depends_on_mission_id"] == "m_b"

    def test_invalid_dependency_type_rejected(self, temp_store):
        """Invalid dependency type is rejected."""
        coordinator = ExecutiveCoordinator(temp_store)

        coordinator.transition_mission("m_a", MissionState.PROPOSED, "init")
        coordinator.transition_mission("m_b", MissionState.PROPOSED, "init")

        success, reason = coordinator.record_dependency(
            "m_a",
            "m_b",
            "INVALID_TYPE",
            "should fail",
        )
        assert not success
        assert "invalid" in reason.lower()

    def test_scheduler_respects_dependencies(self, temp_store):
        """Scheduler doesn't select missions with unsatisfied REQUIRES."""
        coordinator = ExecutiveCoordinator(temp_store)

        # Create and queue missions
        for mission_id in ["m_a", "m_b"]:
            coordinator.transition_mission(mission_id, MissionState.PROPOSED, "init")
            coordinator.transition_mission(mission_id, MissionState.VALIDATED, "validate")
            coordinator.transition_mission(mission_id, MissionState.QUEUED, "queue")

        # m_a requires m_b
        coordinator.record_dependency("m_a", "m_b", "REQUIRES", "a needs b")

        # Scheduler should only select m_b (no dependencies)
        schedulable = coordinator.scheduler.list_schedulable_missions()
        assert "m_b" in schedulable
        assert "m_a" not in schedulable  # blocked by m_b


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
