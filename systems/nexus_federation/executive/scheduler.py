"""F9 Phase C: Persistent Scheduler.

Deterministic mission selection respecting dependencies, priority, and capacity.
"""

from typing import Optional


class ExecutiveScheduler:
    """Scheduler that selects missions from persistent canonical state.

    Does NOT maintain its own queue. Queries FederationStore.
    Does NOT override mission lifecycle. Uses ExecutiveCoordinator transitions.
    """

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.store = coordinator.store

    def list_schedulable_missions(self) -> list[str]:
        """Missions eligible for scheduling.

        Candidates: QUEUED or RETRYABLE states that have no blocking dependencies.
        """
        candidates = []

        for state in ["QUEUED", "RETRYABLE"]:
            mission_ids = self.store.list_missions_by_state(state)
            for mission_id in mission_ids:
                # Check dependencies
                prerequisites = self.store.get_mission_prerequisites(mission_id)
                if not prerequisites:
                    candidates.append(mission_id)
                    continue

                # Check if all REQUIRES satisfied
                from executive.dependency_semantics import evaluate_requires_satisfied

                all_satisfied = True
                for prereq_id in prerequisites:
                    prereq_state = self.store.get_mission_state(prereq_id)
                    deps = self.store.get_mission_dependencies(mission_id)
                    # Find the dependency type for this prerequisite
                    dep_type = None
                    for dep in deps:
                        if dep["depends_on_mission_id"] == prereq_id:
                            dep_type = dep["dependency_type"]
                            break

                    if dep_type == "REQUIRES":
                        if not evaluate_requires_satisfied(mission_id, prereq_id, prereq_state):
                            all_satisfied = False
                            break

                if all_satisfied:
                    candidates.append(mission_id)

        return candidates

    def select_next_mission(self) -> Optional[str]:
        """Deterministically select next mission to execute.

        Tie-breaking: deadline, then mission_id (stable sort).
        """
        candidates = self.list_schedulable_missions()
        if not candidates:
            return None

        # TODO: Sort by deadline/priority when those fields exist
        # For now, stable sort by ID for determinism
        candidates.sort()
        return candidates[0]
