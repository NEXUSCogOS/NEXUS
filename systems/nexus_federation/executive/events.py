"""F9 Phase I: Closed, versioned executive event envelope.

Events are the entry point into the autonomous operating loop. The
envelope is deliberately narrow and closed-vocabulary -- no arbitrary
unvalidated event structures are accepted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class EventType(str, Enum):
    """Closed vocabulary of executive event types."""
    INSTITUTION_REPORT = "INSTITUTION_REPORT"
    EXTERNAL_SIGNAL = "EXTERNAL_SIGNAL"
    MISSION_OUTCOME = "MISSION_OUTCOME"
    MISSION_FAILURE = "MISSION_FAILURE"
    CAPACITY_CHANGE = "CAPACITY_CHANGE"
    DEPENDENCY_RESOLVED = "DEPENDENCY_RESOLVED"
    POLICY_CHANGE = "POLICY_CHANGE"
    ESCALATION_RESOLVED = "ESCALATION_RESOLVED"
    TIMER = "TIMER"
    RECOVERY = "RECOVERY"
    MANUAL_TRIGGER = "MANUAL_TRIGGER"


class EventStatus(str, Enum):
    """Closed vocabulary of event inbox lifecycle states."""
    RECEIVED = "RECEIVED"
    VALIDATED = "VALIDATED"
    DEFERRED = "DEFERRED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    REJECTED = "REJECTED"
    DEAD_LETTER = "DEAD_LETTER"


EVENT_SCHEMA_VERSION = "F9.I.1"

# Bounded retry budget before an event is dead-lettered -- prevents
# spinning forever on a permanently unprocessable event.
MAX_EVENT_ATTEMPTS = 5


@dataclass(frozen=True)
class ExecutiveEvent:
    """Immutable event envelope. References, not copies, for large payloads."""
    event_id: str
    event_type: EventType
    occurred_at: str
    source_institution: Optional[str] = None
    subject: Optional[str] = None
    payload_ref: Optional[str] = None
    evidence_refs: list[str] = field(default_factory=list)
    provenance_refs: list[str] = field(default_factory=list)
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    dedup_key: Optional[str] = None
    policy_context: Optional[str] = None
    received_at: Optional[str] = None
    schema_version: str = EVENT_SCHEMA_VERSION

    def compute_dedup_key(self) -> str:
        """Semantic dedup key when none is supplied explicitly: same type +
        source + subject + occurred_at => same underlying real-world event,
        even across different event_id values (e.g. provider replay with a
        new envelope id)."""
        import hashlib
        basis = f"{self.event_type.value}|{self.source_institution}|{self.subject}|{self.occurred_at}"
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "occurred_at": self.occurred_at,
            "received_at": self.received_at or datetime.now(timezone.utc).isoformat(),
            "source_institution": self.source_institution,
            "subject": self.subject,
            "payload_ref": self.payload_ref,
            "evidence_refs": self.evidence_refs,
            "provenance_refs": self.provenance_refs,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "dedup_key": self.dedup_key or self.compute_dedup_key(),
            "policy_context": self.policy_context,
            "schema_version": self.schema_version,
        }


def is_stale_event(occurred_at_iso: str, staleness_threshold_seconds: float, now: Optional[datetime] = None) -> bool:
    """An event older than the staleness threshold is not trustworthy as
    'current' input -- callers must classify it explicitly, never treat
    every timestamp as fresh."""
    now = now or datetime.now(timezone.utc)
    occurred_at = datetime.fromisoformat(occurred_at_iso)
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    return (now - occurred_at).total_seconds() > staleness_threshold_seconds


def is_future_dated(occurred_at_iso: str, max_clock_skew_seconds: float = 60.0, now: Optional[datetime] = None) -> bool:
    """Detect clock-skew / future-dated events -- must not be blindly trusted."""
    now = now or datetime.now(timezone.utc)
    occurred_at = datetime.fromisoformat(occurred_at_iso)
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    return (occurred_at - now).total_seconds() > max_clock_skew_seconds
