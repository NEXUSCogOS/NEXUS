"""F9 Phase D: Institution Capacity Model.

Tracks per-institution availability, concurrency, and resource pressure.
Persistent (FederationStore), not in-memory-only.
"""

from enum import Enum


class AvailabilityState(str, Enum):
    """Institution availability states."""
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


def is_admissible(capacity_dict: dict) -> bool:
    """True if institution can accept new missions."""
    if capacity_dict is None:
        return False
    if capacity_dict.get("availability_state") == AvailabilityState.UNAVAILABLE.value:
        return False
    if capacity_dict.get("circuit_state") == CircuitState.OPEN.value:
        return False
    active = capacity_dict.get("active_missions", 0)
    max_concurrent = capacity_dict.get("max_concurrent_missions", 5)
    return active < max_concurrent
