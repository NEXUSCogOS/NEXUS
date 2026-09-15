"""F9 Phase H: Executive Memory + Provenance-Linked Recall.

Three conceptual memory classes, ONE canonical persistence authority
(FederationStore). No second global memory authority is created here.

EPISODIC  -- indexes over canonical records (mission_lifecycle_event,
             mission_outcome, learning_event, executive_escalation,
             executive_policy_version, delegation_log, report_log,
             provenance_record). Episode rows carry only linking ids;
             the FULL record body is always re-fetched from its own
             canonical table, never copied wholesale into memory.

SEMANTIC  -- stable executive facts, promoted only from verified/repeated
             evidence, never from a single speculative finding.

PROCEDURAL -- NOT a separate table. Procedural memory IS the Phase G
              executive_policy_version registry; this module only adds a
              read-side convenience (recall_policy_context) over it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class EpisodeType(str, Enum):
    """Closed vocabulary of episode kinds."""
    INSTITUTIONAL_INGEST = "INSTITUTIONAL_INGEST"
    MISSION_LIFECYCLE = "MISSION_LIFECYCLE"
    CROSS_DOMAIN_SYNTHESIS = "CROSS_DOMAIN_SYNTHESIS"
    POLICY_CHANGE = "POLICY_CHANGE"
    ESCALATION = "ESCALATION"
    PRODUCTION = "PRODUCTION"


class SemanticStatus(str, Enum):
    """Closed vocabulary of semantic memory lifecycle states."""
    ACTIVE = "ACTIVE"
    STALE = "STALE"
    CONTRADICTED = "CONTRADICTED"
    INVALIDATED = "INVALIDATED"
    SUPERSEDED = "SUPERSEDED"


class ProvenanceIntegrityStatus(str, Enum):
    """Closed vocabulary for memory-reference integrity failures.

    Memory must fail closed: if source evidence disappears or a hash no
    longer matches, the reference reports one of these, never a silently
    preserved 'verified' fact.
    """
    OK = "OK"
    SOURCE_MISSING = "SOURCE_MISSING"
    EVIDENCE_DRIFT = "EVIDENCE_DRIFT"
    PROVENANCE_BROKEN = "PROVENANCE_BROKEN"


# Claim classes eligible for semantic promotion -- explicit criteria only.
# A single speculative hypothesis is NOT one of these; it stays episodic.
SEMANTIC_PROMOTION_CLAIM_CLASSES = frozenset({
    "AUTHORITY_BOUNDARY",       # e.g. "Sentinel live execution authority is not granted"
    "MODEL_CHARACTERISTIC",     # e.g. "News materiality model is deterministic and uncalibrated"
    "CORPUS_COVERAGE",          # e.g. "Librarian corpus coverage for X is weak"
    "STRUCTURAL_INVARIANT",     # verified architectural fact
    "INSTITUTIONAL_CAPABILITY", # stable capability state, commissioning result
    "VALIDATED_POLICY_FACT",    # a policy fact confirmed by repeated observation
})


@dataclass(frozen=True)
class Episode:
    """Immutable episode-creation record. An INDEX, not a copy of source data."""
    episode_id: str
    episode_type: EpisodeType
    root_trigger_id: Optional[str] = None
    mission_ids: list[str] = field(default_factory=list)
    institution_ids: list[str] = field(default_factory=list)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    outcome_ids: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    provenance_refs: list[str] = field(default_factory=list)
    policy_versions: list[str] = field(default_factory=list)
    status: str = "OPEN"

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "episode_type": self.episode_type.value,
            "root_trigger_id": self.root_trigger_id,
            "mission_ids": self.mission_ids,
            "institution_ids": self.institution_ids,
            "start_time": self.start_time or datetime.now(timezone.utc).isoformat(),
            "end_time": self.end_time,
            "outcome_ids": self.outcome_ids,
            "evidence_refs": self.evidence_refs,
            "provenance_refs": self.provenance_refs,
            "policy_versions": self.policy_versions,
            "status": self.status,
        }


@dataclass(frozen=True)
class SemanticMemoryItem:
    """Immutable semantic memory creation record."""
    semantic_id: str
    statement: str
    claim_class: str
    evidence_refs: list[str] = field(default_factory=list)
    provenance_refs: list[str] = field(default_factory=list)
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    confidence_basis: Optional[str] = None
    status: SemanticStatus = SemanticStatus.ACTIVE
    supersedes_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "semantic_id": self.semantic_id,
            "statement": self.statement,
            "claim_class": self.claim_class,
            "evidence_refs": self.evidence_refs,
            "provenance_refs": self.provenance_refs,
            "valid_from": self.valid_from or datetime.now(timezone.utc).isoformat(),
            "valid_until": self.valid_until,
            "confidence_basis": self.confidence_basis,
            "status": self.status.value,
            "supersedes_id": self.supersedes_id,
        }


def is_eligible_for_semantic_promotion(claim_class: str, sample_size: Optional[int] = None) -> tuple[bool, str]:
    """Explicit promotion criteria -- not every finding becomes semantic memory.

    A single speculative hypothesis (sample_size None or 1, or a claim_class
    outside the closed promotion set) is rejected: it must remain an
    episodic finding until repeated observation, a verified structural
    invariant, a commissioning result, or a validated policy fact supports it.
    """
    if claim_class not in SEMANTIC_PROMOTION_CLAIM_CLASSES:
        return False, f"claim_class {claim_class} not in the closed semantic-promotion set"

    if claim_class == "VALIDATED_POLICY_FACT" and (sample_size is None or sample_size < 2):
        return False, "VALIDATED_POLICY_FACT requires repeated observation (sample_size >= 2)"

    return True, "eligible for semantic promotion"


def similarity_score(
    case_a: dict[str, Any],
    case_b: dict[str, Any],
) -> tuple[float, list[str]]:
    """Transparent baseline similarity: explicit matched-dimension count,
    NOT opaque vector similarity. Returns (score in [0,1], matched_dimensions).

    Dimensions compared: institution_id, episode_type, outcome_class,
    policy_type (of most recent linked policy version) -- each an exact
    equality check on canonical fields, fully explainable.
    """
    dimensions = ["institution_id", "episode_type", "outcome_class", "policy_type"]
    matched = [d for d in dimensions if case_a.get(d) is not None and case_a.get(d) == case_b.get(d)]
    score = len(matched) / len(dimensions)
    return score, matched
