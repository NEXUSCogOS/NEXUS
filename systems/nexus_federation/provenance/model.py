"""Structured provenance record.

New module, NEXUS Federation F2. Replaces the weak, opaque provenance
strings F1 carried (DAT.AI's `provenance_refs: list[str]` is prose, e.g.
"NEXUS_LOCAL donor commit eb9ed1c") with a versioned, structured model that
can be chained into a graph and traced backward.

This module does NOT retroactively force every historical source to
become VERIFIED -- most of this estate's real provenance is honestly
PARTIAL or UNVERIFIED (a donor commit hash that has never been checked
against a live repository, a source file whose original author/timestamp
is not independently confirmed). `verification_status` carries that
honesty explicitly; UNKNOWN provenance stays represented as UNVERIFIED or
MISSING, never silently upgraded.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.0.0"


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"        # hash/existence/timestamp independently checked and matched
    PARTIAL = "PARTIAL"          # some but not all of {existence, hash, timestamp} checked
    UNVERIFIED = "UNVERIFIED"    # claimed but never checked
    INVALID = "INVALID"          # checked and found NOT to match (e.g. hash drift)
    MISSING = "MISSING"          # the referenced source could not be located at all


class ProvenanceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    provenance_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # What kind of thing this record describes, and where it sits in the
    # chain: source document/data -> DAT.AI ingestion -> canonical spatial
    # entity -> DAT.AI finding -> InstitutionalReport -> NEXUS executive
    # state -> DelegationProposal. Not a closed enum: new institutions will
    # introduce their own source_types, and NEXUS must not need a code
    # change to represent them (mirrors institution_type in registry/models.py).
    source_type: str

    source_uri_or_path: Optional[str] = None
    source_hash: Optional[str] = None
    source_timestamp: Optional[str] = None
    observation_timestamp: Optional[str] = None
    ingestion_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    producer: str  # which system/process/institution created this link
    method: str  # how it was produced: "sha256 file hash", "git commit reference", "pydantic model_dump", etc.

    parent_provenance_ids: list[str] = Field(default_factory=list)

    verification_status: VerificationStatus
    verification_method: Optional[str] = None

    @model_validator(mode="after")
    def _verified_requires_method(self):
        if self.verification_status == VerificationStatus.VERIFIED and not self.verification_method:
            raise ValueError(
                "verification_status=VERIFIED requires a stated verification_method "
                "-- a verified claim without a stated method is not a verified claim"
            )
        return self

    @model_validator(mode="after")
    def _invalid_requires_method(self):
        if self.verification_status == VerificationStatus.INVALID and not self.verification_method:
            raise ValueError(
                "verification_status=INVALID requires a stated verification_method "
                "describing how the mismatch was detected"
            )
        return self
