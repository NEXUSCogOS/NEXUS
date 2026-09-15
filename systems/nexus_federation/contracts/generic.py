"""The generic NEXUS Federation institutional reporting contract.

New module, NEXUS Federation F3. DAT.AI's own `institutional.contract`
(a module DAT.AI owns) hardcodes `institution: Literal["dat_ai"]` — correct
for F1/F2, where DAT.AI was the only real institution, but not reusable by
a second one. Per the F3 mission's explicit instruction ("Implement
Librarian's InstitutionalReport adapter using the existing generic
federation contract... Do not create a Librarian-specific federation
parser"), THIS module is the shared, institution-agnostic shape: any
institution builds a report through `build_report()` below with its own
`institution` string, its own capability names, and its own evidence —
never a bespoke parser per institution.

This is deliberately the SAME discipline DAT.AI's own contract embodies
(nothing computes a number/state/claim that isn't traceable to a real
check; UNKNOWN over fabrication; structural self-promotion block), kept
in one place so a THIRD institution (News, YouTube, etc.) can reuse this
directly too, rather than each institution reinventing the same rules.

Capability lifecycle here is a strict SUPERSET of DAT.AI's own
(NOT_IMPLEMENTED..OPERATIONAL, NOT_COMMISSIONED,
EXTERNAL_DEPENDENCY_UNAVAILABLE) plus two additional values the F3 mission
explicitly specifies for Librarian: DEGRADED and UNKNOWN. DAT.AI's own
contract is untouched by this addition — it continues to use its own,
narrower enum.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0.0"


class Confidence(BaseModel):
    """Mirrors DAT.AI's own Confidence discipline: a numeric value requires
    a stated basis; otherwise the value must be the literal 'UNKNOWN'."""

    model_config = ConfigDict(extra="forbid")

    value: Union[Literal["UNKNOWN"], float]
    basis: Optional[str] = None

    @field_validator("value")
    @classmethod
    def _range(cls, v):
        if isinstance(v, float) and not (0.0 <= v <= 1.0):
            raise ValueError("numeric confidence must be within [0.0, 1.0]")
        return v

    @model_validator(mode="after")
    def _numeric_requires_basis(self):
        if isinstance(self.value, float) and not self.basis:
            raise ValueError(
                "a numeric confidence value requires a stated basis -- "
                "an unstated numeric confidence is not accepted"
            )
        return self

    @classmethod
    def unknown(cls) -> "Confidence":
        return cls(value="UNKNOWN", basis=None)


class CapabilityLifecycle(str, Enum):
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    INTEGRATED = "INTEGRATED"
    EMPIRICALLY_VALIDATED = "EMPIRICALLY_VALIDATED"
    OPERATIONAL = "OPERATIONAL"
    NOT_COMMISSIONED = "NOT_COMMISSIONED"
    EXTERNAL_DEPENDENCY_UNAVAILABLE = "EXTERNAL_DEPENDENCY_UNAVAILABLE"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


_SUBSTANTIVE_LIFECYCLES = frozenset(CapabilityLifecycle) - {CapabilityLifecycle.NOT_IMPLEMENTED}


class CapabilityStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    lifecycle: CapabilityLifecycle
    confidence: Confidence = Field(default_factory=Confidence.unknown)
    evidence_refs: list[str] = Field(default_factory=list)
    detail: str = ""
    external_attestation_ref: Optional[str] = None

    @model_validator(mode="after")
    def _substantive_requires_evidence(self):
        if self.lifecycle in _SUBSTANTIVE_LIFECYCLES and not self.evidence_refs:
            raise ValueError(
                f"lifecycle={self.lifecycle.value!r} is substantive and requires "
                f"at least one evidence_ref"
            )
        return self

    @model_validator(mode="after")
    def _operational_requires_attestation(self):
        if self.lifecycle == CapabilityLifecycle.OPERATIONAL and not self.external_attestation_ref:
            raise ValueError(
                "lifecycle=OPERATIONAL requires an external_attestation_ref -- "
                "no institution may self-promote a capability to OPERATIONAL"
            )
        return self


class OperatingState(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    DEGRADED = "DEGRADED"
    RECOVERY_READY = "RECOVERY_READY"
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    INTEGRATED = "INTEGRATED"
    EMPIRICALLY_VALIDATED = "EMPIRICALLY_VALIDATED"
    OPERATIONAL = "OPERATIONAL"


class ResourceUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cpu_seconds: Optional[float] = None
    elapsed_seconds: Optional[float] = None
    peak_memory_bytes: Optional[int] = None
    api_cost_usd: float = 0.0
    model_tokens: int = 0


class StorageState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_bytes: Optional[int] = None
    external_bytes: Optional[int] = None
    external_dependency: bool = False


class InstitutionalReport(BaseModel):
    """The generic NEXUS institutional message envelope, versioned, shared
    across institutions. `institution` is an OPEN string (not a
    Literal locked to one value) -- this is what makes the same class
    reusable by any institution."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    institution: str
    mission_id: str
    cycle_id: str
    timestamp: str

    operating_state: OperatingState
    capability_statuses: list[CapabilityStatus] = Field(default_factory=list)
    objective: str

    observations: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)

    evidence_refs: list[str] = Field(default_factory=list)
    provenance_refs: list[str] = Field(default_factory=list)

    uncertainty: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    actions_completed: list[str] = Field(default_factory=list)
    actions_rejected: list[str] = Field(default_factory=list)
    actions_failed: list[str] = Field(default_factory=list)

    resources: ResourceUsage = Field(default_factory=ResourceUsage)
    storage: StorageState = Field(default_factory=StorageState)

    cross_system_implications: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommended_next_actions: list[str] = Field(default_factory=list)

    executive_attention_required: bool = False
    escalation_reason: Optional[str] = None

    external_attestation_ref: Optional[str] = None

    @field_validator("institution")
    @classmethod
    def _institution_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("institution must be a non-empty string")
        return v

    @model_validator(mode="after")
    def _findings_require_evidence(self):
        if self.findings and not self.evidence_refs:
            raise ValueError(
                "substantive findings require at least one evidence_ref"
            )
        return self

    @model_validator(mode="after")
    def _escalation_reason_requires_flag(self):
        if self.escalation_reason and not self.executive_attention_required:
            raise ValueError(
                "escalation_reason set but executive_attention_required is False"
            )
        return self

    @model_validator(mode="after")
    def _operational_requires_external_attestation(self):
        if self.operating_state == OperatingState.OPERATIONAL and not self.external_attestation_ref:
            raise ValueError(
                "operating_state=OPERATIONAL requires an external_attestation_ref "
                "at the report level -- no institution may self-promote to OPERATIONAL"
            )
        return self


def validate_report(payload: dict) -> InstitutionalReport:
    return InstitutionalReport.model_validate(payload)


def build_report(
    *,
    institution: str,
    mission_id: str,
    objective: str,
    operating_state: OperatingState,
    capability_statuses: list[CapabilityStatus],
    findings: Optional[list[str]] = None,
    evidence_refs: Optional[list[str]] = None,
    provenance_refs: Optional[list[str]] = None,
    limitations: Optional[list[str]] = None,
    uncertainty: Optional[list[str]] = None,
    resources: Optional[ResourceUsage] = None,
    storage: Optional[StorageState] = None,
    cross_system_implications: Optional[list[str]] = None,
    cycle_id: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> InstitutionalReport:
    return InstitutionalReport(
        institution=institution,
        mission_id=mission_id,
        cycle_id=cycle_id or str(uuid.uuid4()),
        timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
        operating_state=operating_state,
        capability_statuses=capability_statuses,
        objective=objective,
        findings=findings or [],
        evidence_refs=evidence_refs or [],
        provenance_refs=provenance_refs or [],
        limitations=limitations or [],
        uncertainty=uncertainty or [],
        resources=resources or ResourceUsage(),
        storage=storage or StorageState(),
        cross_system_implications=cross_system_implications or [],
    )
