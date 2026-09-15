"""YouTube Production core schemas. NEXUS Federation F8.

Every enum/dataclass here corresponds directly to a mission requirement
(sections 5-10, 12-13, 16). This institution PRODUCES media from
evidence other institutions established; it never originates world,
academic, financial, or geospatial truth (mission section 4). Nothing
here is aspirational -- every field is populated by real code in this
package, never a placeholder, and UNKNOWN is used rather than a
fabricated guess wherever a real value is not available.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ======================================================================
# Section 5: Production Mission Contract
# ======================================================================

class ProductionTerminalState(str, Enum):
    RECEIVED = "RECEIVED"
    EVIDENCE_PACK_BUILT = "EVIDENCE_PACK_BUILT"
    SCRIPT_DRAFTED = "SCRIPT_DRAFTED"
    FACT_CHECKED = "FACT_CHECKED"
    MEDIA_PRODUCED = "MEDIA_PRODUCED"
    READY_FOR_PUBLICATION_AUTHORIZATION = "READY_FOR_PUBLICATION_AUTHORIZATION"
    NO_PRODUCTION_ACTION_REQUIRED = "NO_PRODUCTION_ACTION_REQUIRED"
    NO_APPROPRIATE_CHANNEL = "NO_APPROPRIATE_CHANNEL"
    BLOCKED = "BLOCKED"
    REJECTED = "REJECTED"


@dataclass
class ProductionMissionContract:
    production_mission_id: str          # deterministic uuid5, not random -- see mission.py
    parent_trigger_id: Optional[str]
    parent_synthesis_id: Optional[str]
    channel_id: Optional[str]           # None if NO_APPROPRIATE_CHANNEL
    editorial_objective: str
    target_audience: str
    evidence_refs: list[str]
    provenance_refs: list[str]
    allowed_claims: list[str]
    uncertain_claims: list[str]
    prohibited_claims: list[str]
    tone: str
    format: str                         # e.g. "short_form_explainer"
    target_duration_seconds: int
    resource_budget: dict
    rights_constraints: list[str]
    authority: str                      # AuthorityLevel string, GENERATE_INTERNAL for this mission
    success_criteria: list[str]
    terminal_state: str = ProductionTerminalState.RECEIVED.value
    created_at: str = ""


# ======================================================================
# Section 6: Evidence Pack
# ======================================================================

@dataclass
class EvidenceItem:
    evidence_id: str
    source_institution: str            # e.g. "news_intelligence", "nexus_federation", "sentinel"
    source_ref: str                    # the original evidence_ref string
    claim_text: str
    claim_class: str                   # FACT | ANALYSIS | INTERPRETATION | HYPOTHESIS | UNVERIFIED
    uncertainty: Optional[str] = None
    stale: bool = False


@dataclass
class EvidencePack:
    evidence_pack_id: str
    production_mission_id: str
    source_event_ref: str
    nexus_synthesis_ref: Optional[str]
    specialist_findings_refs: list[str]
    items: list[EvidenceItem]
    contradictions: list[str]
    stale_evidence: list[str]
    prohibited_extrapolations: list[str]
    created_at: str = ""


# ======================================================================
# Section 7: Claim Ledger
# ======================================================================

class ClaimVerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    UNVERIFIED = "UNVERIFIED"
    OPINION = "OPINION"
    HYPOTHESIS = "HYPOTHESIS"
    REJECTED = "REJECTED"


@dataclass
class ClaimLedgerEntry:
    claim_id: str
    script_segment: str                # segment identifier this claim appears in
    claim_text: str
    claim_class: str                   # FACT | ANALYSIS | INTERPRETATION | HYPOTHESIS | EDITORIAL_TRANSITION
    evidence_refs: list[str]
    provenance_refs: list[str]
    verification_status: str           # ClaimVerificationStatus value
    uncertainty: Optional[str]
    editorial_transform_status: str    # e.g. "UNCHANGED_FROM_EVIDENCE" | "SIMPLIFIED" | "REWORDED"


# ======================================================================
# Section 8-9: Script
# ======================================================================

class ScriptSegmentClass(str, Enum):
    FACT = "FACT"
    ANALYSIS = "ANALYSIS"
    INTERPRETATION = "INTERPRETATION"
    HYPOTHESIS = "HYPOTHESIS"
    EDITORIAL_TRANSITION = "EDITORIAL_TRANSITION"


@dataclass
class ScriptSegment:
    segment_id: str
    text: str
    segment_class: str                 # ScriptSegmentClass value
    claim_ids: list[str] = field(default_factory=list)


@dataclass
class Script:
    script_id: str
    production_mission_id: str
    segments: list[ScriptSegment]
    revision: int = 1

    def full_text(self) -> str:
        return " ".join(s.text for s in self.segments)


# ======================================================================
# Fact-check stage (section 21)
# ======================================================================

class FactCheckOutcome(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIAL = "PARTIAL"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTORY = "CONTRADICTORY"
    STALE = "STALE"


@dataclass
class FactCheckResult:
    claim_id: str
    outcome: str                       # FactCheckOutcome value
    basis: str
    action_taken: str                  # "NONE" | "REMOVED" | "REWRITTEN"


# ======================================================================
# Section 12: Rights model
# ======================================================================

class RightsStatus(str, Enum):
    CLEARED = "CLEARED"
    LICENSED = "LICENSED"
    OWNED = "OWNED"
    PUBLIC_DOMAIN = "PUBLIC_DOMAIN"
    GENERATED = "GENERATED"
    FAIR_USE_REVIEW_REQUIRED = "FAIR_USE_REVIEW_REQUIRED"
    UNKNOWN = "UNKNOWN"
    REJECTED = "REJECTED"


@dataclass
class RightsRecord:
    asset_id: str
    source: str
    license_status: str                # RightsStatus value
    creator: str
    retrieval_method: str
    usage_basis: str
    modification: str
    attribution_required: bool
    rights_status: str                 # RightsStatus value, duplicated field name mission requires
    usable: bool = False               # derived: True only if rights_status permits use


# ======================================================================
# Generated-media provenance (section 13)
# ======================================================================

@dataclass
class GeneratedAssetRecord:
    asset_id: str
    generator: str                      # e.g. "macos_say", "pillow"
    model_or_voice: str
    prompt_or_reference: str
    generation_timestamp: str
    asset_hash: str
    rights_status: str
    production_mission_id: str
    local_path: str


# ======================================================================
# Render record (section 17)
# ======================================================================

@dataclass
class RenderRecord:
    render_id: str
    production_mission_id: str
    input_script_hash: str
    input_asset_hashes: list[str]
    render_settings: dict
    duration_seconds: float
    resolution: str
    codec: str
    output_hash: str
    output_path: str
    elapsed_compute_seconds: float
    storage_bytes: int
    revision: int = 1


# ======================================================================
# Thumbnail (section 19)
# ======================================================================

@dataclass
class ThumbnailCandidate:
    thumbnail_id: str
    production_mission_id: str
    asset_refs: list[str]
    text: str
    claims: list[str]
    evidence_refs: list[str]
    output_hash: str
    output_path: str
    rights_status: str


# ======================================================================
# Metadata (section 20)
# ======================================================================

@dataclass
class VideoMetadata:
    title: str
    description: str
    chapters: list[str]
    tags: list[str]
    source_notes: list[str]
    disclosure_notes: list[str]


# ======================================================================
# Editorial QC (section 22) -- component states, never a combined score
# ======================================================================

@dataclass
class EditorialQCResult:
    factual_integrity: str
    citation_coverage: str
    evidence_fidelity: str
    audio_quality: str
    visual_integrity: str
    rights_state: str
    caption_accuracy: str
    render_completeness: str
    thumbnail_honesty: str
    metadata_consistency: str
    notes: list[str] = field(default_factory=list)
