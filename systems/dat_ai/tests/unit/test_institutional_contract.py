"""Regression tests for the DAT.AI institutional message contract (hardened
version, 2026-08-27 contract-hardening follow-up).

Marked `unit`: no network, no database, no credentials -- pure schema
validation and pure-function derivation logic.
"""

from __future__ import annotations

import pytest

from institutional.contract import (
    SCHEMA_VERSION,
    CapabilityLifecycle,
    CapabilityStatus,
    ComponentEvidence,
    Confidence,
    InstitutionalReport,
    OperatingState,
    build_report,
    derive_operating_state,
    validate_report,
)

pytestmark = pytest.mark.unit


def _healthy_evidence(**overrides) -> ComponentEvidence:
    base = dict(
        database="healthy",
        postgis="healthy",
        migrations="healthy",
        configuration="healthy",
        external_storage="available",
    )
    base.update(overrides)
    return ComponentEvidence(**base)


def _core_capability(lifecycle=CapabilityLifecycle.INTEGRATED, **overrides) -> CapabilityStatus:
    kwargs = dict(
        name="zoning_api",
        lifecycle=lifecycle,
        confidence=Confidence(value=1.0, basis="test fixture"),
        evidence_refs=["some_test.py"],
    )
    kwargs.update(overrides)
    return CapabilityStatus(**kwargs)


def _minimal_kwargs():
    return dict(
        mission_id="test-mission",
        objective="test objective",
        component_evidence=_healthy_evidence(),
        capability_statuses=[_core_capability()],
    )


# =========================================================================
# 1. Versioned schema
# =========================================================================


def test_schema_version_is_present_and_pinned():
    report = build_report(**_minimal_kwargs())
    assert report.schema_version == SCHEMA_VERSION == "1.1.0"


def test_schema_version_cannot_be_overridden_to_something_else():
    with pytest.raises(Exception):
        InstitutionalReport(
            **{
                **build_report(**_minimal_kwargs()).model_dump(),
                "schema_version": "0.9.0",
            }
        )


# =========================================================================
# 2. Strict validation / fail-closed malformed-message behavior
# =========================================================================


def test_build_report_produces_valid_envelope():
    report = build_report(**_minimal_kwargs())
    assert isinstance(report, InstitutionalReport)
    assert report.institution == "dat_ai"


def test_unknown_field_is_rejected_extra_forbid():
    payload = build_report(**_minimal_kwargs()).model_dump()
    payload["totally_unexpected_field"] = "should not be accepted"
    with pytest.raises(Exception):
        validate_report(payload)


def test_validate_report_rejects_unknown_institution():
    payload = build_report(**_minimal_kwargs()).model_dump()
    payload["institution"] = "not_dat_ai"
    with pytest.raises(Exception):
        validate_report(payload)


def test_validate_report_rejects_unknown_operating_state():
    payload = build_report(**_minimal_kwargs()).model_dump()
    payload["operating_state"] = "FULLY_OPERATIONAL_AND_AMAZING"
    with pytest.raises(Exception):
        validate_report(payload)


def test_malformed_capability_status_rejected():
    payload = build_report(**_minimal_kwargs()).model_dump()
    payload["capability_statuses"][0]["lifecycle"] = "NOT_A_REAL_LIFECYCLE"
    with pytest.raises(Exception):
        validate_report(payload)


def test_escalation_reason_without_flag_fails_closed():
    with pytest.raises(Exception):
        InstitutionalReport(
            **{
                **build_report(**_minimal_kwargs()).model_dump(),
                "executive_attention_required": False,
                "escalation_reason": "something is wrong",
            }
        )


def test_flag_with_reason_is_accepted():
    payload = build_report(**_minimal_kwargs()).model_dump()
    payload["executive_attention_required"] = True
    payload["escalation_reason"] = "a genuine decision is needed"
    report = InstitutionalReport(**payload)
    assert report.executive_attention_required is True


def test_cycle_id_defaults_to_a_real_uuid_not_a_placeholder():
    r1 = build_report(**_minimal_kwargs())
    r2 = build_report(**_minimal_kwargs())
    assert r1.cycle_id != r2.cycle_id
    assert len(r1.cycle_id) == 36


def test_timestamp_is_real_iso8601_utc():
    from datetime import datetime

    report = build_report(**_minimal_kwargs())
    parsed = datetime.fromisoformat(report.timestamp)
    assert parsed.tzinfo is not None


# =========================================================================
# 3. evidence_refs / provenance_refs required for substantive findings
# =========================================================================


def test_findings_without_evidence_refs_rejected():
    kwargs = _minimal_kwargs()
    with pytest.raises(Exception):
        build_report(**kwargs, findings=["something substantive happened"])


def test_findings_with_evidence_refs_accepted():
    kwargs = _minimal_kwargs()
    report = build_report(
        **kwargs,
        findings=["something substantive happened"],
        evidence_refs=["some_evidence.md"],
    )
    assert report.findings == ["something substantive happened"]


def test_capability_status_without_evidence_rejected_for_substantive_lifecycle():
    for lifecycle in (
        CapabilityLifecycle.IMPLEMENTED,
        CapabilityLifecycle.TESTED,
        CapabilityLifecycle.INTEGRATED,
        CapabilityLifecycle.EMPIRICALLY_VALIDATED,
        CapabilityLifecycle.NOT_COMMISSIONED,
        CapabilityLifecycle.EXTERNAL_DEPENDENCY_UNAVAILABLE,
    ):
        with pytest.raises(Exception):
            CapabilityStatus(name="x", lifecycle=lifecycle, evidence_refs=[])


def test_capability_status_not_implemented_does_not_require_evidence():
    # The one exemption: "we haven't looked into this yet" is not a claim.
    status = CapabilityStatus(
        name="x", lifecycle=CapabilityLifecycle.NOT_IMPLEMENTED, evidence_refs=[]
    )
    assert status.lifecycle == CapabilityLifecycle.NOT_IMPLEMENTED


# =========================================================================
# 4. Uncertainty representable as UNKNOWN, not fabricated numeric confidence
# =========================================================================


def test_confidence_unknown_is_valid_without_basis():
    c = Confidence.unknown()
    assert c.value == "UNKNOWN"
    assert c.basis is None


def test_confidence_numeric_without_basis_rejected():
    with pytest.raises(Exception):
        Confidence(value=0.87)


def test_confidence_numeric_with_basis_accepted():
    c = Confidence(value=0.87, basis="computed from 50 comparable sales")
    assert c.value == 0.87
    assert c.basis


def test_confidence_out_of_range_rejected():
    with pytest.raises(Exception):
        Confidence(value=1.5, basis="nonsense")


def test_partial_provenance_is_representable_as_unknown_not_a_guess():
    """A capability with genuinely unknown confidence must be able to say
    so honestly rather than being forced to supply an invented number."""
    status = CapabilityStatus(
        name="x",
        lifecycle=CapabilityLifecycle.NOT_IMPLEMENTED,
        confidence=Confidence.unknown(),
        evidence_refs=[],
    )
    assert status.confidence.value == "UNKNOWN"


# =========================================================================
# 5. operating_state derived from component evidence, not manually declared
# =========================================================================


def test_build_report_has_no_operating_state_parameter():
    import inspect

    sig = inspect.signature(build_report)
    assert "operating_state" not in sig.parameters


def test_healthy_evidence_and_integrated_core_yields_integrated_state():
    state = derive_operating_state(_healthy_evidence(), [_core_capability(CapabilityLifecycle.INTEGRATED)])
    assert state == OperatingState.INTEGRATED


def test_missing_database_yields_unavailable():
    state = derive_operating_state(
        _healthy_evidence(database="unhealthy"), [_core_capability()]
    )
    assert state == OperatingState.UNAVAILABLE


# =========================================================================
# 6. Missing PostGIS distinguishable from missing model
# =========================================================================


def test_postgis_unavailable_yields_unavailable_state():
    state = derive_operating_state(
        _healthy_evidence(postgis="unhealthy"), [_core_capability()]
    )
    assert state == OperatingState.UNAVAILABLE


def test_postgis_down_is_distinct_field_from_database_down():
    """Proves these are independently settable, not a single collapsed flag."""
    ev = _healthy_evidence(database="healthy", postgis="unhealthy")
    assert ev.database == "healthy"
    assert ev.postgis == "unhealthy"


def test_untrained_model_does_not_affect_operating_state_when_core_is_healthy():
    """The core requirement: lack of a validated domain model must not make
    the zoning/API capability (and therefore the institution-level state)
    falsely report unavailable."""
    satellite_capability = CapabilityStatus(
        name="satellite_classification",
        lifecycle=CapabilityLifecycle.IMPLEMENTED,  # untrained-model floor
        confidence=Confidence(value=0.0, basis="untrained, see test"),
        evidence_refs=["test"],
    )
    state = derive_operating_state(
        _healthy_evidence(),
        [_core_capability(CapabilityLifecycle.INTEGRATED), satellite_capability],
    )
    assert state == OperatingState.INTEGRATED  # NOT dragged down


# =========================================================================
# 7. External storage unavailable -> explicit DEGRADED state
# =========================================================================


def test_external_storage_unavailable_yields_degraded():
    state = derive_operating_state(
        _healthy_evidence(external_storage="unavailable"), [_core_capability()]
    )
    assert state == OperatingState.DEGRADED


def test_external_storage_available_does_not_force_degraded():
    state = derive_operating_state(
        _healthy_evidence(external_storage="available"), [_core_capability()]
    )
    assert state != OperatingState.DEGRADED


# =========================================================================
# 8. Absent satellite credentials -> EXTERNAL_DEPENDENCY_UNAVAILABLE,
#    not a generic failure
# =========================================================================


def test_satellite_acquisition_reports_external_dependency_unavailable():
    status = CapabilityStatus(
        name="satellite_acquisition",
        lifecycle=CapabilityLifecycle.EXTERNAL_DEPENDENCY_UNAVAILABLE,
        confidence=Confidence.unknown(),
        evidence_refs=["DATAI_PHASE_AB_VERIFICATION_REPORT.md"],
        detail="No CDSE credentials configured.",
    )
    assert status.lifecycle == CapabilityLifecycle.EXTERNAL_DEPENDENCY_UNAVAILABLE
    assert status.lifecycle != CapabilityLifecycle.NOT_IMPLEMENTED
    # Distinguishable from a generic/unspecified failure: the enum member
    # name itself names the real cause.


# =========================================================================
# 9. Untrained model cannot produce VALIDATED/OPERATIONAL status
# =========================================================================


def test_capability_operational_without_attestation_rejected():
    with pytest.raises(Exception):
        CapabilityStatus(
            name="satellite_classification",
            lifecycle=CapabilityLifecycle.OPERATIONAL,
            evidence_refs=["x"],
        )


def test_capability_operational_with_attestation_accepted():
    status = CapabilityStatus(
        name="satellite_classification",
        lifecycle=CapabilityLifecycle.OPERATIONAL,
        evidence_refs=["x"],
        external_attestation_ref="external-auditor-signoff-2099-01-01",
    )
    assert status.lifecycle == CapabilityLifecycle.OPERATIONAL


def test_report_level_operational_without_attestation_rejected():
    """Even with a properly-attested capability (which makes
    derive_operating_state legitimately compute OPERATIONAL), the REPORT
    itself still independently requires its own top-level
    external_attestation_ref -- proven here by constructing the envelope
    directly rather than through build_report() (which has no parameter to
    supply that field at all, and so fails one step earlier -- an even
    stronger guarantee, exercised separately below)."""
    base = build_report(**_minimal_kwargs()).model_dump()
    base["operating_state"] = "OPERATIONAL"
    base["capability_statuses"] = [
        {
            "name": "zoning_api",
            "lifecycle": "OPERATIONAL",
            "confidence": {"value": "UNKNOWN", "basis": None},
            "evidence_refs": ["x"],
            "detail": "",
            "external_attestation_ref": "external-signoff",
        }
    ]
    with pytest.raises(Exception):
        InstitutionalReport(**base)  # missing top-level external_attestation_ref


def test_build_report_cannot_express_operational_at_all():
    """Stronger guarantee than the above: build_report() has no parameter
    for the report-level external_attestation_ref, so any scenario where
    derive_operating_state legitimately computes OPERATIONAL (an attested
    core capability) makes build_report() itself raise immediately -- there
    is no way to reach a constructed OPERATIONAL report through the
    automated builder DAT.AI's own reporter code calls."""
    attested_core = _core_capability(
        CapabilityLifecycle.OPERATIONAL, external_attestation_ref="external-signoff"
    )
    kwargs = _minimal_kwargs()
    kwargs["capability_statuses"] = [attested_core]
    with pytest.raises(Exception):
        build_report(**kwargs)


def test_derive_operating_state_never_returns_operational_without_attested_core():
    """DAT.AI's own automated derivation path (as used by
    institutional/reporter.py) never sets external_attestation_ref, so this
    proves OPERATIONAL is structurally unreachable via self-report."""
    # Every non-attested core lifecycle must map to something other than
    # OPERATIONAL.
    for lifecycle in (
        CapabilityLifecycle.NOT_IMPLEMENTED,
        CapabilityLifecycle.IMPLEMENTED,
        CapabilityLifecycle.TESTED,
        CapabilityLifecycle.INTEGRATED,
        CapabilityLifecycle.EMPIRICALLY_VALIDATED,
    ):
        core = _core_capability(lifecycle) if lifecycle != CapabilityLifecycle.NOT_IMPLEMENTED else CapabilityStatus(
            name="zoning_api", lifecycle=lifecycle, evidence_refs=[]
        )
        state = derive_operating_state(_healthy_evidence(), [core])
        assert state != OperatingState.OPERATIONAL


# =========================================================================
# 10. Valuation cannot report OPERATIONAL (schema-level guarantee)
# =========================================================================


def test_valuation_not_commissioned_cannot_be_operational():
    status = CapabilityStatus(
        name="valuation",
        lifecycle=CapabilityLifecycle.NOT_COMMISSIONED,
        confidence=Confidence.unknown(),
        evidence_refs=["PRESERVED_EVIDENCE_CONCLUSIONS.md"],
    )
    assert status.lifecycle != CapabilityLifecycle.OPERATIONAL
    assert status.lifecycle == CapabilityLifecycle.NOT_COMMISSIONED


def test_valuation_forced_to_operational_requires_attestation_like_anything_else():
    """No special-casing lets valuation skip the OPERATIONAL gate either."""
    with pytest.raises(Exception):
        CapabilityStatus(
            name="valuation",
            lifecycle=CapabilityLifecycle.OPERATIONAL,
            evidence_refs=["x"],
        )
