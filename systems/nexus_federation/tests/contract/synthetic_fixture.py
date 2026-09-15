"""Synthetic TEST FIXTURE institution contract.

NEXUS Federation F2. This module exists ONLY to prove, in
tests/contract/test_second_institution_generic.py, that
`ingress/contract_registry.py`'s dispatch mechanism needs no code change
to accept a second, genuinely differently-shaped institution -- different
institution id, different schema_version string, different capability
names, different capability-status field set than DAT.AI's contract.

This is explicitly NOT a claimed real institution, NOT wired into
production code anywhere, and NOT registered by default -- the test that
uses it registers and unregisters it itself.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

FIXTURE_SCHEMA_VERSION = "0.1.0-test-fixture"
FIXTURE_INSTITUTION_ID = "test_fixture_institution"


class FixtureOperatingState(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    DEGRADED = "DEGRADED"
    RESEARCH_ACTIVE = "RESEARCH_ACTIVE"  # deliberately NOT one of DAT.AI's operating_state values


class FixtureCapabilityLifecycle(str, Enum):
    """A deliberately different vocabulary than DAT.AI's
    CapabilityLifecycle -- proving the kernel treats lifecycle values as
    opaque strings (see state/capability.py's own docstring on this) and
    never assumes DAT.AI's specific ladder. Kept as a str Enum (not a bare
    string) because that IS a genuine, disclosed cross-institution contract
    requirement -- see SECOND_INSTITUTION_ENTRY_PROTOCOL.md: every
    institution's `capability_statuses[].lifecycle` must expose `.value`,
    exactly like DAT.AI's own contract does."""

    DRAFT = "DRAFT"
    PEER_REVIEWED = "PEER_REVIEWED"
    PUBLISHED = "PUBLISHED"
    RETRACTED = "RETRACTED"


class FixtureCapabilityStatus(BaseModel):
    """Deliberately a different field set than DAT.AI's CapabilityStatus
    (no `confidence` object at all) -- proving the kernel only relies on
    `name`, `lifecycle`, `evidence_refs`, `detail`."""

    model_config = ConfigDict(extra="forbid")
    name: str
    lifecycle: FixtureCapabilityLifecycle
    evidence_refs: list[str] = Field(default_factory=list)
    detail: str = ""


class SyntheticInstitutionReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = FIXTURE_SCHEMA_VERSION
    institution: str = FIXTURE_INSTITUTION_ID
    mission_id: str
    cycle_id: str
    timestamp: str

    operating_state: FixtureOperatingState
    capability_statuses: list[FixtureCapabilityStatus] = Field(default_factory=list)
    objective: str

    findings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    provenance_refs: list[str] = Field(default_factory=list)


def validate_fixture_report(payload: dict[str, Any]) -> SyntheticInstitutionReport:
    return SyntheticInstitutionReport.model_validate(payload)
