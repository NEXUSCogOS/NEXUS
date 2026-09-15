"""Academic source provenance model.

NEW module, NEXUS Librarian F4. Every field the mission requires (section
8), with `UNKNOWN` as the honest default rather than a fabricated value.
`retraction_status`/`correction_status` (section 9) are tracked so a
retracted source never silently remains ordinary evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from academic.taxonomy import SourceType

UNKNOWN = "UNKNOWN"


class RetractionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CORRECTED = "CORRECTED"
    RETRACTED = "RETRACTED"
    SUPERSEDED = "SUPERSEDED"
    UNKNOWN = "UNKNOWN"


class VerificationStatus(str, Enum):
    """Mirrors nexus_federation.provenance.model.VerificationStatus's
    vocabulary for consistency across the federation, defined locally
    (not imported) so librarian's academic module has no hard import-time
    dependency on nexus_federation being on the path."""

    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    UNVERIFIED = "UNVERIFIED"
    INVALID = "INVALID"
    MISSING = "MISSING"


class AcademicProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str  # see academic/identity.py -- external ID preferred, content-addressed fallback
    title: str
    authors: list[str] = Field(default_factory=list)
    publication_date: str = UNKNOWN
    journal_or_venue: str = UNKNOWN
    publisher: str = UNKNOWN
    doi: str = UNKNOWN
    external_identifiers: dict[str, str] = Field(default_factory=dict)  # e.g. {"arxiv": "2104.08663"}
    canonical_url: str = UNKNOWN
    source_type: SourceType
    peer_review_status: str = UNKNOWN  # descriptive text; source_type already carries the formal category
    retrieval_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    content_hash: str = UNKNOWN
    license: str = UNKNOWN
    language: str = UNKNOWN
    version: str = UNKNOWN
    retraction_status: RetractionStatus = RetractionStatus.UNKNOWN
    correction_status: str = "NONE"
    ingestion_method: str
    verification_status: VerificationStatus

    @model_validator(mode="after")
    def _retracted_requires_note(self):
        if self.retraction_status == RetractionStatus.RETRACTED and self.correction_status == "NONE":
            object.__setattr__(self, "correction_status", "RETRACTION_NOTED_NO_FURTHER_CORRECTION_DETAIL")
        return self

    @model_validator(mode="after")
    def _at_least_one_identifier(self):
        if self.doi == UNKNOWN and not self.external_identifiers and self.canonical_url == UNKNOWN:
            raise ValueError(
                "an academic source requires at least one of doi/external_identifiers/"
                "canonical_url -- a source with zero identifying information cannot be "
                "recorded (it would be indistinguishable from a fabricated entry)"
            )
        return self
