"""Semantic core: Foundation implementing all principles (audit, connectivity, learning, types, Python practices)"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import (
    Any, Callable, Dict, Final, Generator, List, Literal, Mapping, Optional,
    Protocol, Sequence
)
from uuid import UUID, uuid4

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated

# Type aliases (semantic meaning embedded in types)
SemanticID = Annotated[UUID, "Unique semantic identifier"]
MetricValue = Annotated[float, "Performance metric on 0-1 scale"]
ConfidenceScore = Annotated[float, "Confidence level 0-1"]


# ════════════════════════════════════════════════════════════════════════════
# PART 1: SEMANTIC PROTOCOLS (Contracts, not implementations)
# ════════════════════════════════════════════════════════════════════════════

class SemanticEntity(Protocol):
    """Minimal protocol: all semantic entities implement these operations"""

    @property
    def semantic_id(self) -> UUID:
        """Unique identifier (immutable)"""
        ...

    @property
    def semantic_type(self) -> str:
        """Type of entity (Decision, Outcome, Lesson, etc.)"""
        ...

    def to_semantic_dict(self) -> Dict[str, Any]:
        """Convert to semantic representation (for serialization)"""
        ...


class Evaluable(Protocol):
    """Anything that can be evaluated against standards"""

    def evaluate_against_manifest(self) -> ManifestAlignment:
        """Evaluate against optimal structure"""
        ...

    def compare_against_frontier(self) -> List[FrontierComparison]:
        """Compare against frontier research"""
        ...


class Auditable(Protocol):
    """Anything that produces audit entries"""

    def to_audit_entry(self) -> AuditEntry:
        """Generate audit record"""
        ...

    def previous_state(self) -> Optional[Dict[str, Any]]:
        """Get state before change"""
        ...


class Learnable(Protocol):
    """Anything that generates knowledge"""

    def extract_lessons(self) -> List[Lesson]:
        """Extract knowledge from outcomes"""
        ...

    def generate_procedure(self) -> Optional[Procedure]:
        """Consolidate into reusable procedure"""
        ...


class EventEmitter(Protocol):
    """Anything that emits events"""

    def emit_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Emit event to bus"""
        ...


# ════════════════════════════════════════════════════════════════════════════
# PART 2: ENUMS (Semantic states)
# ════════════════════════════════════════════════════════════════════════════

class DecisionStatus(Enum):
    """Semantic states of a decision"""
    PROPOSED = auto()
    EVALUATED = auto()
    APPROVED = auto()
    IMPLEMENTED = auto()
    SUPERSEDED = auto()


class OperationType(str, Enum):
    """Semantic audit operations"""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    SUPERSEDE = "SUPERSEDE"
    DELETE = "DELETE"
    DERIVE = "DERIVE"


class AuditLevel(str, Enum):
    """Compliance levels"""
    SILENT = "SILENT"
    BASIC = "BASIC"
    STANDARD = "STANDARD"
    COMPLIANCE = "COMPLIANCE"
    FORENSIC = "FORENSIC"


# ════════════════════════════════════════════════════════════════════════════
# PART 3: SEMANTIC ENTITIES (Immutable dataclasses)
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AuditEntry:
    """Immutable audit trail entry"""

    entity_id: Final[UUID]
    entity_type: Final[str]
    operation: Final[OperationType]
    id: Final[UUID] = field(default_factory=uuid4)
    timestamp: Final[datetime] = field(default_factory=lambda: datetime.now(timezone.utc))
    previous_state: Final[Optional[Dict[str, Any]]] = None
    new_state: Final[Optional[Dict[str, Any]]] = None
    actor: Final[str] = "system"
    reason: Final[str] = ""
    state_hash: Final[str] = ""  # SHA256 for chain verification

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for storage"""
        return {
            'id': str(self.id),
            'timestamp': self.timestamp.isoformat(),
            'entity_id': str(self.entity_id),
            'entity_type': self.entity_type,
            'operation': self.operation.value,
            'previous_state': self.previous_state,
            'new_state': self.new_state,
            'actor': self.actor,
            'reason': self.reason
        }


@dataclass(frozen=True)
class Decision:
    """Semantic Decision entity"""

    decision_type: str
    capability_affected: str
    hypothesis: str
    current_state: Mapping[str, MetricValue]
    projected_outcome: Mapping[str, MetricValue]
    decision_rationale: str
    semantic_id: Final[UUID] = field(default_factory=uuid4)
    semantic_type: Final[str] = field(default='Decision', init=False)
    status: DecisionStatus = DecisionStatus.PROPOSED
    created_at: Final[datetime] = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Final[str] = "system"
    manifest_alignment: Optional[ManifestAlignment] = None
    frontier_comparisons: Sequence[FrontierComparison] = field(default_factory=tuple)
    outcome: Optional[Outcome] = None

    def to_semantic_dict(self) -> Dict[str, Any]:
        """Convert to semantic representation"""
        return {
            'id': str(self.semantic_id),
            'type': self.semantic_type,
            'decision_type': self.decision_type,
            'capability': self.capability_affected,
            'hypothesis': self.hypothesis,
            'current_state': dict(self.current_state),
            'projected_outcome': dict(self.projected_outcome),
            'status': self.status.name,
            'created_at': self.created_at.isoformat()
        }

    def __call__(self, manifest: 'ManifestAlignment') -> 'Decision':
        """Evaluate against manifest: decision(manifest)"""
        return Decision(
            **{**self.__dict__,
               'manifest_alignment': manifest,
               'status': DecisionStatus.EVALUATED}
        )

    def __getitem__(self, metric: str) -> MetricValue:
        """Access metric: decision['accuracy']"""
        return self.projected_outcome[metric]


@dataclass(frozen=True)
class ManifestAlignment:
    """Evaluation against optimal structure"""

    decision_id: Final[UUID]
    capability: str
    current_value: MetricValue
    optimal_value: MetricValue
    priority: Literal['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
    recommendation: Literal['STRONGLY_RECOMMEND', 'RECOMMEND', 'CONDITIONAL', 'REJECT']
    id: Final[UUID] = field(default_factory=uuid4)
    gap: Final[MetricValue] = field(init=False)
    alignment_score: ConfidenceScore = 0.5

    def __post_init__(self) -> None:
        object.__setattr__(self, 'gap', self.optimal_value - self.current_value)


@dataclass(frozen=True)
class FrontierComparison:
    """Comparison against frontier research"""

    decision_id: Final[UUID]
    frontier_study: str
    frontier_value: MetricValue
    studio_value: MetricValue
    id: Final[UUID] = field(default_factory=uuid4)
    exceeds_frontier: Final[bool] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'exceeds_frontier', self.studio_value > self.frontier_value)


@dataclass(frozen=True)
class Outcome:
    """Results after implementation"""

    decision_id: Final[UUID]
    actual_metrics: Mapping[str, MetricValue]
    vs_projected: Mapping[str, Any]
    id: Final[UUID] = field(default_factory=uuid4)
    side_effects: Sequence[str] = field(default_factory=tuple)
    success: bool = True
    recorded_at: Final[datetime] = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class Lesson:
    """Knowledge extracted from outcome"""

    outcome_id: Final[UUID]
    hypothesis_validity: Literal['Confirmed', 'Rejected', 'Partial', 'Uncertain']
    id: Final[UUID] = field(default_factory=uuid4)
    unexpected_findings: Sequence[str] = field(default_factory=tuple)
    improvements: Sequence[str] = field(default_factory=tuple)
    confidence: ConfidenceScore = 0.6


@dataclass(frozen=True)
class Procedure:
    """Learned pattern for reuse"""

    name: str
    decision_pattern: str
    capability: str
    id: Final[UUID] = field(default_factory=uuid4)
    steps: Sequence[str] = field(default_factory=tuple)
    effectiveness_score: ConfidenceScore = 0.5
    usage_count: int = 0


# ════════════════════════════════════════════════════════════════════════════
# PART 4: EVENT BUS (Loose coupling via events)
# ════════════════════════════════════════════════════════════════════════════

class EventBus:
    """Local event bus (Tier 1 connectivity)"""

    def __init__(self) -> None:
        self.handlers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable[[Dict[str, Any]], None]) -> UUID:
        """Subscribe to event type"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []

        self.handlers[event_type].append(handler)
        return uuid4()

    def emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Emit event (no exceptions propagate)"""
        if event_type in self.handlers:
            for handler in self.handlers[event_type]:
                try:
                    handler(payload)
                except Exception as e:
                    # Log but don't fail
                    print(f"Event handler error for {event_type}: {e}")


# ════════════════════════════════════════════════════════════════════════════
# PART 5: AUDIT MANAGER (Immutable trail)
# ════════════════════════════════════════════════════════════════════════════

class AuditManager:
    """Manages audit trail (Audit-first)"""

    def __init__(self, level: AuditLevel = AuditLevel.STANDARD) -> None:
        self.level = level
        self.entries: List[AuditEntry] = []

    def record(
        self,
        entity_id: UUID,
        entity_type: str,
        operation: OperationType,
        previous_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None,
        reason: str = ""
    ) -> AuditEntry:
        """Record immutable audit entry"""
        entry = AuditEntry(
            entity_id=entity_id,
            entity_type=entity_type,
            operation=operation,
            previous_state=previous_state,
            new_state=new_state,
            reason=reason
        )

        if self.level != AuditLevel.SILENT:
            self.entries.append(entry)

        return entry

    def get_history(self, entity_id: UUID) -> List[AuditEntry]:
        """Get complete history (immutable)"""
        return [e for e in self.entries if e.entity_id == entity_id]

    def verify_chain(self) -> bool:
        """Verify audit chain integrity"""
        # In real implementation: check SHA256 hashes
        return len(self.entries) > 0


# ════════════════════════════════════════════════════════════════════════════
# PART 6: SEMANTIC TRANSACTION (Context manager)
# ════════════════════════════════════════════════════════════════════════════

@contextmanager
def semantic_transaction(
    audit: AuditManager,
    entity_id: UUID,
    entity_type: str,
    operation: OperationType,
    previous_state: Optional[Dict[str, Any]] = None,
    reason: str = ""
) -> Generator[None, None, None]:
    """Context manager for semantic operations"""
    try:
        yield
        # Success: record audit entry
        audit.record(entity_id, entity_type, operation, previous_state=previous_state, reason=reason)
    except Exception as e:
        # Failure: still record (for forensics)
        audit.record(entity_id, entity_type, operation, reason=f"FAILED: {str(e)}")
        raise


# ════════════════════════════════════════════════════════════════════════════
# PART 7: STREAMING QUERIES (Low memory)
# ════════════════════════════════════════════════════════════════════════════

class SemanticStore:
    """Persistent semantic storage"""

    def __init__(self, db_path: str) -> None:
        self.db = sqlite3.connect(db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize semantic schema"""
        cursor = self.db.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS decisions (
                semantic_id TEXT PRIMARY KEY,
                semantic_type TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                capability_affected TEXT NOT NULL,
                hypothesis TEXT,
                current_state JSON,
                projected_outcome JSON,
                status TEXT,
                created_at DATETIME
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_entries (
                id TEXT PRIMARY KEY,
                timestamp DATETIME,
                entity_id TEXT,
                entity_type TEXT,
                operation TEXT,
                previous_state JSON,
                new_state JSON,
                reason TEXT
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_entity_id ON audit_entries(entity_id)')
        self.db.commit()

    def stream_decisions(
        self,
        decision_type: Optional[str] = None,
        batch_size: int = 1000
    ) -> Generator[Decision, None, None]:
        """Stream decisions without loading all in memory"""
        cursor = self.db.cursor()

        query = "SELECT * FROM decisions"
        if decision_type:
            query += f" WHERE decision_type = '{decision_type}'"

        cursor.execute(query)

        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break

            for row in rows:
                yield Decision(
                    semantic_id=UUID(row[0]),
                    decision_type=row[2],
                    capability_affected=row[3],
                    hypothesis=row[4],
                    current_state=dict(row[5] or {}),
                    projected_outcome=dict(row[6] or {}),
                    decision_rationale="",
                    status=DecisionStatus[row[7] or 'PROPOSED']
                )


# ════════════════════════════════════════════════════════════════════════════
# PART 8: REFERENCE EXAMPLE (All principles working together)
# ════════════════════════════════════════════════════════════════════════════

class SemanticKernel:
    """Reference implementation showing all principles"""

    def __init__(self, db_path: str = '.nexus_semantic.db', audit_level: AuditLevel = AuditLevel.STANDARD):
        self.audit = AuditManager(audit_level)
        self.bus = EventBus()
        self.store = SemanticStore(db_path)

    def propose_decision(
        self,
        decision_type: str,
        capability: str,
        hypothesis: str,
        current: Dict[str, float],
        projected: Dict[str, float],
        rationale: str
    ) -> Decision:
        """Propose decision (audit + event)"""
        decision = Decision(
            decision_type=decision_type,
            capability_affected=capability,
            hypothesis=hypothesis,
            current_state=current,
            projected_outcome=projected,
            decision_rationale=rationale
        )

        # Audit: immutable record of creation
        with semantic_transaction(self.audit, decision.semantic_id, 'Decision', OperationType.CREATE):
            # Event: notify listeners
            self.bus.emit('decision.proposed', decision.to_semantic_dict())

        return decision

    def evaluate_decision(
        self,
        decision: Decision,
        manifest: ManifestAlignment
    ) -> Decision:
        """Evaluate decision (audit + event)"""
        evaluated = Decision(**{**decision.__dict__, 'manifest_alignment': manifest, 'status': DecisionStatus.EVALUATED})

        # Audit: record evaluation
        with semantic_transaction(self.audit, decision.semantic_id, 'Decision', OperationType.UPDATE):
            # Event: notify listeners
            self.bus.emit('decision.evaluated', {'decision_id': str(decision.semantic_id), 'recommendation': manifest.recommendation})

        return evaluated

    def record_outcome(self, outcome: Outcome) -> Outcome:
        """Record outcome (audit + event + learning)"""
        with semantic_transaction(self.audit, outcome.id, 'Outcome', OperationType.CREATE):
            # Event: trigger learning
            self.bus.emit('outcome.recorded', {'id': str(outcome.id), 'success': outcome.success})

        return outcome

    def extract_lessons(self, outcome: Outcome) -> List[Lesson]:
        """Extract lessons (learnable protocol)"""
        lessons = [
            Lesson(
                outcome_id=outcome.id,
                hypothesis_validity='Confirmed' if outcome.success else 'Rejected',
                unexpected_findings=list(outcome.side_effects) if outcome.side_effects else [],
                confidence=0.9 if outcome.success else 0.5
            )
        ]

        # Audit: record lessons extracted
        for lesson in lessons:
            with semantic_transaction(self.audit, lesson.id, 'Lesson', OperationType.DERIVE, reason=f"From outcome {outcome.id}"):
                # Event: knowledge generated
                self.bus.emit('lesson.extracted', {'outcome_id': str(outcome.id), 'validity': lesson.hypothesis_validity})

        return lessons

    def to_dict(self) -> Dict[str, Any]:
        return {
            'audit_entries': len(self.audit.entries),
            'audit_level': self.audit.level.value
        }
