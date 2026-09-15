"""NEXUS Executive Institution Capacity Model.

F9 hardening: track per-institution availability and load.

NEXUS must know: is this institution free? is it overloaded?
what failed last time? when is it next available?

Do not delegate to an unavailable institution without explicit
degraded-mode policy.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class InstitutionHealthState(str, Enum):
    """Health state of an institution."""

    HEALTHY = "HEALTHY"  # operational, available
    DEGRADED = "DEGRADED"  # operational, but at reduced capacity
    UNHEALTHY = "UNHEALTHY"  # not operational, failures recent
    UNKNOWN = "UNKNOWN"  # never heard from, or data stale


@dataclass
class InstitutionCapacity:
    """Availability and load for one institution."""

    institution_id: str

    # Current state
    health_state: InstitutionHealthState = InstitutionHealthState.UNKNOWN
    current_missions: int = 0  # how many missions is this institution running?
    max_concurrent_missions: int = 5  # policy ceiling (prevents runaway)
    queue_depth: int = 0  # how many missions are waiting?

    # Resource usage
    estimated_utilization_percent: float = 0.0  # 0-100
    peak_rss_bytes: Optional[float] = None  # current memory estimate
    last_cpu_measurement_seconds: Optional[float] = None

    # Failure tracking
    last_failure_at: Optional[str] = None  # ISO 8601
    failure_count_recent: int = 0  # failures in last 24h
    last_failure_reason: Optional[str] = None
    circuit_breaker_open: bool = False  # open = temporarily disabled

    # Availability
    next_available_at: Optional[str] = None  # ISO 8601
    expected_availability_percent: float = 1.0  # historical uptime

    # Recent performance
    mean_mission_duration_seconds: Optional[float] = None
    last_successful_mission_at: Optional[str] = None

    # Metadata
    last_status_update: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    authority_ceiling: Optional[str] = None  # what authority can we delegate to this inst.?

    def is_available(self) -> bool:
        """True if this institution can accept new missions."""
        if self.circuit_breaker_open:
            return False
        if self.health_state == InstitutionHealthState.UNHEALTHY:
            return False
        if self.current_missions >= self.max_concurrent_missions:
            return False
        if self.health_state == InstitutionHealthState.UNKNOWN:
            # Unknown state: can try, but with caution
            return True
        return True

    def available_slots(self) -> int:
        """How many additional missions can this institution take?"""
        if not self.is_available():
            return 0
        return max(0, self.max_concurrent_missions - self.current_missions)

    def utilization_pressure(self) -> str:
        """How much pressure: relaxed / normal / high / critical."""
        percent = self.estimated_utilization_percent
        if percent < 30:
            return "relaxed"
        elif percent < 70:
            return "normal"
        elif percent < 90:
            return "high"
        else:
            return "critical"

    def retry_eligible(self) -> bool:
        """Can we retry a failed mission on this institution?"""
        # Unhealthy or unknown: only retry if alternative doesn't exist.
        if self.health_state in (InstitutionHealthState.UNHEALTHY, InstitutionHealthState.UNKNOWN):
            return self.failure_count_recent < 5
        return True


@dataclass
class InstitutionCapacityRegistry:
    """Global registry of all institution capacity states."""

    institutions: dict[str, InstitutionCapacity] = field(default_factory=dict)

    def register_institution(self, inst_id: str, max_concurrent: int = 5, authority_ceiling: Optional[str] = None):
        """Register or update an institution's capacity profile."""
        if inst_id not in self.institutions:
            self.institutions[inst_id] = InstitutionCapacity(
                institution_id=inst_id,
                max_concurrent_missions=max_concurrent,
                authority_ceiling=authority_ceiling,
            )

    def get_institution(self, inst_id: str) -> Optional[InstitutionCapacity]:
        """Get the capacity info for an institution."""
        return self.institutions.get(inst_id)

    def find_available(self, max_queue_delay: Optional[int] = None) -> list[str]:
        """Return list of available institution IDs, sorted by utilization (best first).

        max_queue_delay (seconds): if a queue would delay this mission beyond this,
        exclude that institution.
        """
        available = []
        for inst_id, cap in self.institutions.items():
            if not cap.is_available():
                continue
            if max_queue_delay is not None and cap.queue_depth > 0:
                # Rough estimate: assume each mission takes 60s on average.
                estimated_delay = cap.queue_depth * 60
                if estimated_delay > max_queue_delay:
                    continue
            available.append(inst_id)

        # Sort by utilization (lowest first).
        available.sort(
            key=lambda inst_id: self.institutions[inst_id].estimated_utilization_percent
        )
        return available

    def record_mission_started(self, inst_id: str, mission_id: str):
        """Note that an institution has claimed a mission."""
        cap = self.get_institution(inst_id)
        if cap:
            cap.current_missions += 1
            cap.health_state = InstitutionHealthState.HEALTHY

    def record_mission_completed(self, inst_id: str, mission_id: str, elapsed_seconds: float):
        """Note that a mission completed successfully."""
        cap = self.get_institution(inst_id)
        if cap:
            cap.current_missions = max(0, cap.current_missions - 1)
            cap.queue_depth = max(0, cap.queue_depth - 1)
            cap.failure_count_recent = max(0, cap.failure_count_recent - 1)
            cap.last_successful_mission_at = datetime.now(timezone.utc).isoformat()
            if cap.mean_mission_duration_seconds is None:
                cap.mean_mission_duration_seconds = elapsed_seconds
            else:
                # Running average.
                cap.mean_mission_duration_seconds = (
                    (cap.mean_mission_duration_seconds * 0.7) + (elapsed_seconds * 0.3)
                )

    def record_mission_failed(self, inst_id: str, mission_id: str, reason: str):
        """Note that a mission failed."""
        cap = self.get_institution(inst_id)
        if cap:
            cap.current_missions = max(0, cap.current_missions - 1)
            cap.failure_count_recent += 1
            cap.last_failure_at = datetime.now(timezone.utc).isoformat()
            cap.last_failure_reason = reason

            # Circuit breaker: if too many failures, open it.
            if cap.failure_count_recent >= 5:
                cap.circuit_breaker_open = True
                cap.health_state = InstitutionHealthState.UNHEALTHY

    def record_heartbeat(self, inst_id: str, alive: bool, utilization_percent: float):
        """Record a heartbeat from an institution."""
        cap = self.get_institution(inst_id)
        if cap:
            cap.last_status_update = datetime.now(timezone.utc).isoformat()
            cap.estimated_utilization_percent = utilization_percent
            if alive:
                if cap.circuit_breaker_open and cap.failure_count_recent < 2:
                    # Circuit breaker reset: start half-open.
                    cap.circuit_breaker_open = False
                    cap.health_state = InstitutionHealthState.DEGRADED
                elif cap.health_state in (InstitutionHealthState.DEGRADED, InstitutionHealthState.UNHEALTHY):
                    cap.health_state = InstitutionHealthState.HEALTHY
