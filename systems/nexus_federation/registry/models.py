"""NEXUS institution registry — the canonical record of what NEXUS knows
about each federated institution.

New module, NEXUS Federation F1. Every field here is populated from
accepted evidence (an ingested, validated InstitutionalReport) or is an
explicit registration-time constant (institution_id, canonical_path) --
never a manually-asserted "healthy"/"good" judgment.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from state.capability import ComponentState


class InstitutionRegistryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institution_id: str
    institution_type: str  # e.g. "geospatial_intelligence" -- descriptive, not enforced against a closed vocabulary yet
    canonical_path: str
    contract_version: str
    authority_class: str = "A1_OBSERVATION"  # per the directive's delegated-authority tiers; DAT.AI has made no A3+ claim
    maturity: str  # the institution's own reported operating_state, verbatim
    last_report_timestamp: Optional[str] = None
    last_verified_cycle: Optional[str] = None
    component_states: list[ComponentState] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    external_dependencies: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    storage_dependencies: list[str] = Field(default_factory=list)
    registered_at: str
