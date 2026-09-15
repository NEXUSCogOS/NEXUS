"""F9 Phase C: Dependency Semantics and Validation.

Explicit dependency types and cycle detection.
"""

from enum import Enum
from typing import Optional


class DependencyType(str, Enum):
    """Canonical dependency relationship types."""
    REQUIRES = "REQUIRES"  # hard prerequisite
    OPTIONAL = "OPTIONAL"  # does not block
    BLOCKED_BY = "BLOCKED_BY"  # reverse: this blocks other
    INVALIDATED_BY = "INVALIDATED_BY"  # evidence invalidates
    SUPERSEDES = "SUPERSEDES"  # newer replaces older


def validate_dependency_type(dep_type: str) -> bool:
    """True if dep_type is a valid DependencyType."""
    try:
        DependencyType(dep_type)
        return True
    except ValueError:
        return False


def detect_cycle(
    mission_id: str,
    predecessor_map: dict[str, list[str]],  # mission_id -> list of prerequisites
    visited: Optional[set[str]] = None,
    rec_stack: Optional[set[str]] = None,
) -> bool:
    """Detect if adding this mission creates a cycle.

    Returns True if cycle exists.
    Uses DFS: visited tracks all seen nodes; rec_stack tracks current path.
    """
    visited = visited or set()
    rec_stack = rec_stack or set()

    visited.add(mission_id)
    rec_stack.add(mission_id)

    for prerequisite in predecessor_map.get(mission_id, []):
        if prerequisite not in visited:
            if detect_cycle(prerequisite, predecessor_map, visited, rec_stack):
                return True
        elif prerequisite in rec_stack:
            # Back edge: cycle found
            return True

    rec_stack.remove(mission_id)
    return False


def evaluate_requires_satisfied(
    mission_id: str,
    prerequisite_id: str,
    prerequisite_state: Optional[str],
    satisfied_terminal_states: set[str] = None,
) -> bool:
    """Determine if a REQUIRES dependency is satisfied.

    A REQUIRES dependency is satisfied when the prerequisite reaches
    an acceptable terminal state (typically COMPLETED).

    Args:
        mission_id: the dependent mission
        prerequisite_id: the required mission
        prerequisite_state: current state of prerequisite
        satisfied_terminal_states: which terminal states count as satisfied (default: {COMPLETED})

    Returns True if prerequisite is satisfied.
    """
    satisfied_terminal_states = satisfied_terminal_states or {"COMPLETED"}

    if prerequisite_state is None:
        return False  # Prerequisite doesn't exist
    if prerequisite_state in satisfied_terminal_states:
        return True
    return False
