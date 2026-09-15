"""DAT.AI's NEXUS institutional reporting contract — hardened version.

Written during DAT.AI Phase C (2026-08-27), extended the same day per an
explicit follow-up mission requiring: a versioned schema, strict validation,
evidence/provenance requirements for substantive findings, an honest
UNKNOWN-capable confidence representation, per-capability lifecycle tracking
distinguished from a single institution-level operating_state, and a
structural (not just conventional) block on DAT.AI self-promoting to
OPERATIONAL.

Design principle carried through every model below: nothing here computes a
number, a state, or a claim that isn't traceable to a real check. Where no
real check exists, the correct value is UNKNOWN or a lifecycle stage short
of what would need one -- never a plausible-looking placeholder.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.1.0"


# =========================================================================
# Confidence — the honest-uncertainty primitive
# =========================================================================


class Confidence(BaseModel):
    """A confidence value that can be explicitly UNKNOWN.

    Per the hardening requirement: uncertainty must be representable as
    UNKNOWN rather than forcing a fabricated numeric confidence. A numeric
    value MUST carry a `basis` explaining what it was computed from --
    a bare number with no stated origin is exactly the kind of unsupported
    claim this contract exists to prevent.
    """

    model_config = ConfigDict(extra="forbid")

    value: Union[Literal["UNKNOWN"], float]
    basis: Optional[str] = None

    @field_validator("value")
    @classmethod
    def _numeric_value_must_be_a_real_fraction(cls, v):
        if isinstance(v, float) and not (0.0 <= v <= 1.0):
            raise ValueError("numeric confidence must be within [0.0, 1.0]")
        return v

    @model_validator(mode="after")
    def _numeric_requires_basis(self):
        if isinstance(self.value, float) and not self.basis:
            raise ValueError(
                "a numeric confidence value requires a `basis` describing "
                "what it was computed from -- use value='UNKNOWN' if there "
                "is no real computation behind a number"
            )
        return self

    @classmethod
    def unknown(cls) -> "Confidence":
        return cls(value="UNKNOWN", basis=None)


# =========================================================================
# Capability lifecycle — per-capability, not institution-wide
# =========================================================================


class CapabilityLifecycle(str, Enum):
    """Per the directive's capability lifecycle, plus two DAT.AI-specific
    terminal states that are not failures but honest classifications:
    NOT_COMMISSIONED (capability exists but is not authorized/wired -- e.g.
    valuation) and EXTERNAL_DEPENDENCY_UNAVAILABLE (capability is blocked on
    a real external dependency that is confirmed absent -- e.g. satellite
    acquisition without CDSE credentials). Neither of these is a defect in
    DAT.AI's own code; conflating them with a generic "failed" would hide
    the real reason.
    """

    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    INTEGRATED = "INTEGRATED"
    EMPIRICALLY_VALIDATED = "EMPIRICALLY_VALIDATED"
    OPERATIONAL = "OPERATIONAL"
    NOT_COMMISSIONED = "NOT_COMMISSIONED"
    EXTERNAL_DEPENDENCY_UNAVAILABLE = "EXTERNAL_DEPENDENCY_UNAVAILABLE"


_SUBSTANTIVE_LIFECYCLES = frozenset(
    {
        CapabilityLifecycle.IMPLEMENTED,
        CapabilityLifecycle.TESTED,
        CapabilityLifecycle.INTEGRATED,
        CapabilityLifecycle.EMPIRICALLY_VALIDATED,
        CapabilityLifecycle.OPERATIONAL,
        CapabilityLifecycle.NOT_COMMISSIONED,
        CapabilityLifecycle.EXTERNAL_DEPENDENCY_UNAVAILABLE,
    }
)
# Only NOT_IMPLEMENTED is exempt from requiring evidence -- it is the "we
# have not looked into this yet" default, not a specific claim. Every other
# lifecycle, including the two DAT.AI-specific terminal states, asserts
# something concrete (blocked on a named external dependency; deliberately
# not authorized) and must cite what that assertion is based on.


class CapabilityStatus(BaseModel):
    """One capability's real, independently-evidenced lifecycle state.

    A capability's maturity is tracked separately from every other
    capability and separately from the institution-level operating_state --
    per the hardening requirement, an unpromoted/untrained model must not
    make an otherwise-working zoning API falsely report as unavailable.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    lifecycle: CapabilityLifecycle
    confidence: Confidence = Field(default_factory=Confidence.unknown)
    evidence_refs: list[str] = Field(default_factory=list)
    detail: str = ""
    # Only ever set by an external authority verifying this specific
    # capability -- DAT.AI's own automated reporting code (institutional/
    # reporter.py) never sets this field. Its absence is precisely what
    # makes OPERATIONAL structurally unreachable by self-report; see
    # `_operational_requires_external_attestation` below.
    external_attestation_ref: Optional[str] = None

    @field_validator("evidence_refs")
    @classmethod
    def _substantive_lifecycle_requires_evidence(cls, v, info):
        lifecycle = info.data.get("lifecycle")
        if lifecycle in _SUBSTANTIVE_LIFECYCLES and not v:
            raise ValueError(
                f"lifecycle={lifecycle!r} is a substantive claim and "
                f"requires at least one evidence_ref"
            )
        return v

    @model_validator(mode="after")
    def _operational_requires_external_attestation(self):
        if (
            self.lifecycle == CapabilityLifecycle.OPERATIONAL
            and not self.external_attestation_ref
        ):
            raise ValueError(
                "CapabilityLifecycle.OPERATIONAL requires an "
                "external_attestation_ref. DAT.AI's own automated "
                "derivation must never self-promote a capability to "
                "OPERATIONAL -- that determination belongs to an external "
                "authority, recorded here by reference, not asserted by "
                "the institution about itself."
            )
        return self


# =========================================================================
# Component evidence — the real, checkable inputs operating_state is
# derived from. Never set operating_state directly; derive it from these.
# =========================================================================


class ComponentEvidence(BaseModel):
    """Real component states, one field per independently-checkable thing.

    Deliberately separate fields for database/postgis (so a PostGIS-specific
    outage is distinguishable from a generic database outage) and for
    external_storage (so an unreachable model-weights volume is an explicit,
    named degraded condition rather than folded into a generic "unhealthy").
    """

    model_config = ConfigDict(extra="forbid")

    database: Literal["healthy", "unhealthy", "unavailable"]
    postgis: Literal["healthy", "unhealthy", "unavailable"]
    migrations: Literal["healthy", "unhealthy"]
    configuration: Literal["healthy", "unhealthy"]
    external_storage: Literal["available", "unavailable", "degraded", "unknown"] = "unknown"


class OperatingState(str, Enum):
    """Institution-level state. Per the hardening requirement, this is
    ALWAYS computed by `derive_operating_state()` from ComponentEvidence +
    the core capability's own CapabilityStatus -- InstitutionalReport does
    not accept it as a free-form constructor argument (see build_report()).
    """

    UNAVAILABLE = "UNAVAILABLE"
    DEGRADED = "DEGRADED"
    RECOVERY_READY = "RECOVERY_READY"
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    INTEGRATED = "INTEGRATED"
    EMPIRICALLY_VALIDATED = "EMPIRICALLY_VALIDATED"
    OPERATIONAL = "OPERATIONAL"


_LIFECYCLE_TO_OPERATING_STATE = {
    CapabilityLifecycle.NOT_IMPLEMENTED: OperatingState.DEGRADED,
    CapabilityLifecycle.IMPLEMENTED: OperatingState.IMPLEMENTED,
    CapabilityLifecycle.TESTED: OperatingState.TESTED,
    CapabilityLifecycle.INTEGRATED: OperatingState.INTEGRATED,
    CapabilityLifecycle.EMPIRICALLY_VALIDATED: OperatingState.EMPIRICALLY_VALIDATED,
    # CapabilityLifecycle.OPERATIONAL is intentionally NOT mapped as a
    # simple lookup -- see derive_operating_state() below, which re-checks
    # the external_attestation_ref explicitly rather than trusting the map.
}


def derive_operating_state(
    component_evidence: ComponentEvidence,
    capability_statuses: list[CapabilityStatus],
    *,
    core_capability_name: str = "zoning_api",
) -> OperatingState:
    """The ONLY function that produces an operating_state.

    Order of evaluation matters and is deliberate:
    1. Database or PostGIS unavailable/unhealthy -> UNAVAILABLE, full stop.
       (PostGIS is checked as its own field, distinguishable from a bare
       database connectivity failure -- see ComponentEvidence.)
    2. External storage confirmed unavailable -> DEGRADED, explicitly.
    3. Migrations unhealthy or configuration unhealthy -> DEGRADED.
    4. Otherwise, the institution-level state reflects the CORE capability
       (zoning_api by default) specifically -- NOT the least-mature
       capability across the whole institution. A satellite model that is
       untrained, or a valuation capability that is not commissioned, must
       not drag a working zoning API down to a falsely worse state.
    5. OPERATIONAL is only reachable if the core capability's own
       CapabilityStatus is already OPERATIONAL -- which itself required an
       external_attestation_ref at construction (enforced by
       CapabilityStatus's own validator). DAT.AI's own reporter never sets
       that field, so this function can never manufacture OPERATIONAL out
       of component health alone.
    """
    if component_evidence.database != "healthy":
        return OperatingState.UNAVAILABLE
    if component_evidence.postgis != "healthy":
        return OperatingState.UNAVAILABLE

    if component_evidence.external_storage == "unavailable":
        return OperatingState.DEGRADED

    if component_evidence.migrations != "healthy":
        return OperatingState.DEGRADED
    if component_evidence.configuration != "healthy":
        return OperatingState.DEGRADED

    core = next(
        (c for c in capability_statuses if c.name == core_capability_name), None
    )
    if core is None:
        # No evidence at all about the core capability -- do not guess.
        return OperatingState.DEGRADED

    if core.lifecycle == CapabilityLifecycle.OPERATIONAL:
        # Only reachable because CapabilityStatus itself already enforced
        # external_attestation_ref is present -- re-confirmed here, not
        # trusted blindly, in case a future refactor loosens that model.
        if not core.external_attestation_ref:
            raise ValueError(
                "unreachable in principle: a CapabilityStatus with "
                "lifecycle=OPERATIONAL but no external_attestation_ref "
                "should have failed its own validation before reaching "
                "this function"
            )
        return OperatingState.OPERATIONAL

    return _LIFECYCLE_TO_OPERATING_STATE.get(core.lifecycle, OperatingState.DEGRADED)


# =========================================================================
# Resource / storage state (unchanged shape from the first contract pass)
# =========================================================================


class ResourceUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu: Optional[float] = None
    memory: Optional[float] = None
    local_storage: Optional[int] = None
    external_storage: Optional[int] = None
    storage_delta: Optional[int] = None
    model_tokens: Optional[int] = None
    api_cost: Optional[float] = None
    elapsed_compute: Optional[float] = None


class StorageState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hot_bytes: Optional[int] = None
    external_active_bytes: Optional[int] = None
    warm_bytes: Optional[int] = None
    cold_bytes: Optional[int] = None
    local_growth: Optional[int] = None
    external_dependency_status: Literal[
        "available", "unavailable", "degraded", "unknown"
    ] = "unknown"


# =========================================================================
# The envelope
# =========================================================================


class InstitutionalReport(BaseModel):
    """The standard NEXUS institutional message envelope, versioned."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.1.0"] = SCHEMA_VERSION
    institution: Literal["dat_ai"] = "dat_ai"
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

    @model_validator(mode="after")
    def _findings_require_evidence(self):
        if self.findings and not self.evidence_refs:
            raise ValueError(
                "substantive findings require at least one evidence_ref "
                "(directive: 'evidence_refs and provenance_refs required "
                "for substantive findings')"
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
        if (
            self.operating_state == OperatingState.OPERATIONAL
            and not self.external_attestation_ref
        ):
            raise ValueError(
                "operating_state=OPERATIONAL requires an "
                "external_attestation_ref at the report level -- DAT.AI "
                "must never self-promote to OPERATIONAL"
            )
        return self


def build_report(
    *,
    mission_id: str,
    objective: str,
    component_evidence: ComponentEvidence,
    capability_statuses: list[CapabilityStatus],
    observations: list[str] | None = None,
    findings: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    provenance_refs: list[str] | None = None,
    uncertainty: list[str] | None = None,
    limitations: list[str] | None = None,
    actions_completed: list[str] | None = None,
    actions_rejected: list[str] | None = None,
    actions_failed: list[str] | None = None,
    resources: ResourceUsage | None = None,
    storage: StorageState | None = None,
    cross_system_implications: list[str] | None = None,
    risks: list[str] | None = None,
    recommended_next_actions: list[str] | None = None,
    executive_attention_required: bool = False,
    escalation_reason: str | None = None,
    cycle_id: str | None = None,
    core_capability_name: str = "zoning_api",
) -> InstitutionalReport:
    """Construct and validate one institutional report.

    `operating_state` is NOT a parameter here -- per the hardening
    requirement it is always derived from `component_evidence` and
    `capability_statuses` via `derive_operating_state()`. There is no code
    path in this function that lets a caller manually declare it.
    """
    operating_state = derive_operating_state(
        component_evidence, capability_statuses, core_capability_name=core_capability_name
    )

    return InstitutionalReport(
        mission_id=mission_id,
        cycle_id=cycle_id or str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        operating_state=operating_state,
        capability_statuses=capability_statuses,
        objective=objective,
        observations=observations or [],
        findings=findings or [],
        evidence_refs=evidence_refs or [],
        provenance_refs=provenance_refs or [],
        uncertainty=uncertainty or [],
        limitations=limitations or [],
        actions_completed=actions_completed or [],
        actions_rejected=actions_rejected or [],
        actions_failed=actions_failed or [],
        resources=resources or ResourceUsage(),
        storage=storage or StorageState(),
        cross_system_implications=cross_system_implications or [],
        risks=risks or [],
        recommended_next_actions=recommended_next_actions or [],
        executive_attention_required=executive_attention_required,
        escalation_reason=escalation_reason,
    )


def validate_report(payload: dict[str, Any]) -> InstitutionalReport:
    """Validate an arbitrary payload against the contract.

    Raises pydantic.ValidationError on any malformed message -- this IS the
    fail-closed behavior the directive requires. Callers must not catch and
    silently ignore this exception. `extra="forbid"` on every model in this
    module means an unknown field anywhere in the payload also fails closed.
    """
    return InstitutionalReport.model_validate(payload)
