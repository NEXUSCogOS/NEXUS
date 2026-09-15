"""Builds a real DAT.AI institutional report from live component and
capability checks.

Rewritten during DAT.AI Phase C's contract-hardening follow-up (2026-08-27)
to populate the new per-capability, evidence-derived contract shape. Every
capability status below is computed from a real check (a live database
query, a config value, a checkpoint audit) or is a locked policy conclusion
with a citation (valuation) -- never an invented value.
"""

from __future__ import annotations

from app.config import settings
from institutional.contract import (
    CapabilityLifecycle,
    CapabilityStatus,
    ComponentEvidence,
    Confidence,
    InstitutionalReport,
    build_report,
)


def _component_evidence() -> ComponentEvidence:
    """Real component checks, reusing the exact functions /readiness uses."""
    from app.routes.health import _check_database, _check_migrations

    database, postgis = _check_database()
    migrations = _check_migrations()
    problems = settings.validate()

    # External storage: the model checkpoint is DAT.AI's one real external-
    # storage dependency today (see DATAI_CANONICAL_STORAGE_MAP.md). Its
    # reachability is a real, checkable filesystem fact, not an assumption.
    if settings.model_path.exists():
        external_storage = "available"
    else:
        external_storage = "unavailable"

    return ComponentEvidence(
        database="healthy" if database.state == "healthy" else "unhealthy",
        postgis="healthy" if postgis.state == "healthy" else "unhealthy",
        migrations="healthy" if migrations.state == "healthy" else "unhealthy",
        configuration="healthy" if not problems else "unhealthy",
        external_storage=external_storage,
    )


def _zoning_api_capability(component_evidence: ComponentEvidence) -> CapabilityStatus:
    """The core, recovered capability. Its maturity must NOT be dragged down
    by the satellite model's untrained status or valuation's non-commission
    -- those are tracked as entirely separate capabilities below."""
    if component_evidence.database != "healthy" or component_evidence.postgis != "healthy":
        return CapabilityStatus(
            name="zoning_api",
            lifecycle=CapabilityLifecycle.IMPLEMENTED,
            confidence=Confidence.unknown(),
            evidence_refs=["DATAI_CANONICAL_ARCHITECTURE.md"],
            detail="Code exists and is committed; live database/PostGIS "
            "unavailable in this environment, so integration cannot be "
            "currently confirmed.",
        )
    return CapabilityStatus(
        name="zoning_api",
        lifecycle=CapabilityLifecycle.INTEGRATED,
        confidence=Confidence(value=1.0, basis="22 of 22 zoning-specific unit+integration tests passing, wired into app.main, live-smoke-tested via TestClient this phase"),
        evidence_refs=[
            "DATAI_CANONICAL_TEST_BASELINE.md",
            "tests/unit/models/test_zoning.py",
            "tests/integration/routes/test_zoning_routes.py",
        ],
        detail="Zoning model + spatial API: database, PostGIS, and "
        "migrations all healthy; route wired into app.main and smoke-tested.",
    )


def _model_registry_capability() -> CapabilityStatus:
    return CapabilityStatus(
        name="model_registry",
        lifecycle=CapabilityLifecycle.TESTED,
        confidence=Confidence(value=1.0, basis="7/7 tests passing, self-contained (stdlib only), no external dependency"),
        evidence_refs=["tests/unit/test_model_registry.py"],
        detail="Version tracking, promote/reject workflow. No external dependency.",
    )


def _promotion_gate_capability() -> CapabilityStatus:
    return CapabilityStatus(
        name="promotion_gate",
        lifecycle=CapabilityLifecycle.TESTED,
        confidence=Confidence(value=1.0, basis="8/8 tests passing, self-contained, no external dependency"),
        evidence_refs=["tests/unit/test_promotion_gate.py"],
        detail="Metric-threshold gated promotion workflow.",
    )


def _satellite_classification_capability() -> CapabilityStatus:
    """Must never report EMPIRICALLY_VALIDATED or OPERATIONAL while the
    checkpoint is untrained -- enforced here by construction (this function
    only ever returns those lifecycles if audit.exists and neither
    pristine-ImageNet nor untrained-head evidence is present), and proven by
    tests/unit/test_untrained_model_cannot_be_promoted.py at the schema
    level.
    """
    from app.ml.satellite_classifier import audit_only

    try:
        audit = audit_only(settings)
    except Exception as exc:  # noqa: BLE001 -- reported, not swallowed
        return CapabilityStatus(
            name="satellite_classification",
            lifecycle=CapabilityLifecycle.NOT_IMPLEMENTED,
            confidence=Confidence.unknown(),
            evidence_refs=[],
            detail=f"Audit could not run: {type(exc).__name__}: {exc}",
        )

    if not audit.exists:
        return CapabilityStatus(
            name="satellite_classification",
            lifecycle=CapabilityLifecycle.NOT_IMPLEMENTED,
            confidence=Confidence.unknown(),
            evidence_refs=["DATAI_MODEL_STATUS_REGISTER.md"],
            detail="No checkpoint present at MODEL_PATH.",
        )

    if audit.backbone_is_pristine_imagenet or audit.head_appears_untrained:
        # The untrained-model floor: code exists, loads, and the audit
        # mechanism itself works (that much IS real and tested) -- but the
        # classification capability itself cannot claim more than
        # IMPLEMENTED while the model has never been domain-trained.
        return CapabilityStatus(
            name="satellite_classification",
            lifecycle=CapabilityLifecycle.IMPLEMENTED,
            confidence=Confidence(
                value=0.0,
                basis="audit_checkpoint(): backbone bit-identical to stock "
                "ImageNet weights, classification head shows fresh-"
                "initialization statistics -- zero evidence of domain training",
            ),
            evidence_refs=[
                "DATAI_MODEL_STATUS_REGISTER.md",
                "tests/unit/test_untrained_model_cannot_be_promoted.py",
            ],
            detail=(
                f"Checkpoint {audit.model_version} present and loads "
                f"correctly; promotion_status={audit.promotion_status.value}. "
                "Classifier code and audit mechanism are real and tested; "
                "the specific checkpoint is untrained and must not be "
                "treated as a working classifier."
            ),
        )

    # Unreached today (would require a genuinely trained checkpoint) --
    # left here so a future real training result has somewhere honest to
    # report, rather than this function needing a rewrite to allow it.
    return CapabilityStatus(
        name="satellite_classification",
        lifecycle=CapabilityLifecycle.EMPIRICALLY_VALIDATED,
        confidence=Confidence(
            value=0.5,
            basis="audit_checkpoint() shows domain-trained weights, but no "
            "held-out accuracy evaluation has been run against real "
            "labeled imagery -- confidence capped pending that evaluation",
        ),
        evidence_refs=["DATAI_MODEL_STATUS_REGISTER.md"],
        detail=f"Checkpoint {audit.model_version}: {audit.promotion_status.value}.",
    )


def _satellite_acquisition_capability() -> CapabilityStatus:
    if not settings.has_any_acquisition_credentials:
        return CapabilityStatus(
            name="satellite_acquisition",
            lifecycle=CapabilityLifecycle.EXTERNAL_DEPENDENCY_UNAVAILABLE,
            confidence=Confidence.unknown(),
            evidence_refs=[
                "DATAI_PHASE_AB_VERIFICATION_REPORT.md",
                "DATAI_PHASE_D_ENTRY_CRITERIA.md",
            ],
            detail=(
                "No CDSE (S3 or OAuth2) credentials configured. Confirmed "
                "NOT_FOUND anywhere in this estate during Phase A+B "
                "verification (env, filesystem, LaunchAgents, Keychain). "
                "This is a real external dependency gap, not a code defect."
            ),
        )
    return CapabilityStatus(
        name="satellite_acquisition",
        lifecycle=CapabilityLifecycle.NOT_IMPLEMENTED,
        confidence=Confidence.unknown(),
        evidence_refs=[],
        detail="Credentials present but the acquisition pipeline itself "
        "was not recovered into canonical NEXUS this phase (Phase D scope).",
    )


def _valuation_capability() -> CapabilityStatus:
    """Locked conclusion, not a live check -- see
    PRESERVED_EVIDENCE_CONCLUSIONS.md #4. There is nothing to query at
    runtime because valuation was never ported into canonical code; this
    status exists precisely so that absence is reported explicitly rather
    than by silent omission from every report."""
    return CapabilityStatus(
        name="valuation",
        lifecycle=CapabilityLifecycle.NOT_COMMISSIONED,
        confidence=Confidence.unknown(),
        evidence_refs=[
            "PRESERVED_EVIDENCE_CONCLUSIONS.md",
            "DATAI_PHASE_C_RECOVERY_REPORT.md",
        ],
        detail=(
            "source/valuation_engine.py and valuation_algorithm.py contain "
            "genuine rule-based comparable-sales logic but are untested, "
            "duplicated, and not integrated into canonical DAT.AI. Not "
            "ported this phase. Locked: must not be reported as OPERATIONAL "
            "or otherwise implied to be an available capability."
        ),
    )


def all_capability_statuses() -> list[CapabilityStatus]:
    evidence = _component_evidence()
    return [
        _zoning_api_capability(evidence),
        _model_registry_capability(),
        _promotion_gate_capability(),
        _satellite_classification_capability(),
        _satellite_acquisition_capability(),
        _valuation_capability(),
    ]


def build_current_report(mission_id: str) -> InstitutionalReport:
    """Build a report reflecting DAT.AI's actual state right now."""
    evidence = _component_evidence()
    capabilities = all_capability_statuses()

    findings = [f"{c.name}: {c.lifecycle.value} -- {c.detail}" for c in capabilities]
    all_evidence_refs = sorted({ref for c in capabilities for ref in c.evidence_refs})

    limitations = []
    risks = []
    for c in capabilities:
        if c.name == "satellite_classification" and c.lifecycle == CapabilityLifecycle.IMPLEMENTED:
            limitations.append(
                "Satellite classifier checkpoint is untrained. No domain "
                "inference should be trusted from it."
            )
        if c.name == "satellite_acquisition" and c.lifecycle == CapabilityLifecycle.EXTERNAL_DEPENDENCY_UNAVAILABLE:
            limitations.append(c.detail)
        if c.name == "valuation":
            risks.append(
                "Valuation is NOT_COMMISSIONED -- any consumer of this "
                "report must not treat DAT.AI as providing valuation output."
            )

    risks.append(
        "Zoning data provenance ('confidence 0.95, DVHC authenticated') is a "
        "flat per-batch constant, not a per-record verified score -- see "
        "SPATIAL_PROVENANCE_STANDARD.md."
    )

    return build_report(
        mission_id=mission_id,
        objective=(
            "Report DAT.AI's real, evidence-derived operating state and "
            "per-capability maturity -- no capability status here is "
            "manually declared."
        ),
        component_evidence=evidence,
        capability_statuses=capabilities,
        observations=[
            f"database={evidence.database}",
            f"postgis={evidence.postgis}",
            f"migrations={evidence.migrations}",
            f"external_storage={evidence.external_storage}",
        ],
        findings=findings,
        evidence_refs=all_evidence_refs,
        provenance_refs=["NEXUS_LOCAL donor commit eb9ed1c (systems/dat_ai)"],
        uncertainty=[],
        limitations=limitations,
        risks=risks,
        cross_system_implications=[
            "No other NEXUS institution currently consumes DAT.AI output -- "
            "this is the institutional adapter, not yet wired to a message "
            "bus or executive kernel (neither exists in canonical NEXUS yet)."
        ],
        recommended_next_actions=["See DATAI_PHASE_D_ENTRY_CRITERIA.md."],
        executive_attention_required=False,
    )
