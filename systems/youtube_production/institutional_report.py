"""YouTube Production's InstitutionalReport builder. NEXUS Federation F8,
mission section 25. Uses the SAME generic contract Librarian/Sentinel/
News Intelligence use (`contracts.generic`) -- no YouTube-specific
federation parser.

`publication` is ALWAYS reported NOT_COMMISSIONED here -- this
institution's authority ceiling is GENERATE_INTERNAL, and no code path in
this package ever attempts an upload, so there is never a real
`external_attestation_ref` to report for it, and it is never claimed
OPERATIONAL.
"""

from __future__ import annotations

import sys
from pathlib import Path

FEDERATION_ROOT = str(Path(__file__).resolve().parent.parent / "nexus_federation")
if FEDERATION_ROOT not in sys.path:
    sys.path.insert(0, FEDERATION_ROOT)

from contracts.generic import (
    CapabilityLifecycle,
    CapabilityStatus,
    Confidence,
    OperatingState,
    ResourceUsage,
    StorageState,
    build_report,
)


def build_youtube_report(
    *,
    mission_id: str,
    production_mission_id: str,
    terminal_state: str,
    evidence_pack,
    script,
    fact_check_results: list,
    render_record,
    thumbnail,
    metadata,
    rights_usable: list,
    rights_blocked: list,
    qc_result,
    resource_usage: dict,
    storage_usage: dict,
) -> dict:
    unsupported_removed = [r for r in fact_check_results if r.outcome == "UNSUPPORTED"]

    capability_statuses = [
        CapabilityStatus(
            name="evidence_pack",
            lifecycle=CapabilityLifecycle.TESTED if evidence_pack else CapabilityLifecycle.NOT_IMPLEMENTED,
            confidence=Confidence(value=0.6, basis="built deterministically from a real cross-domain synthesis's own findings"),
            evidence_refs=[i.evidence_id for i in evidence_pack.items] or ["no_evidence_items"],
            detail=f"{len(evidence_pack.items)} evidence item(s), {len(evidence_pack.contradictions)} contradiction(s)",
        ),
        CapabilityStatus(
            name="script",
            lifecycle=CapabilityLifecycle.TESTED if script.segments else CapabilityLifecycle.NOT_IMPLEMENTED,
            confidence=Confidence(value=0.5, basis="every FACT/ANALYSIS/INTERPRETATION/HYPOTHESIS segment traces to one evidence item"),
            evidence_refs=[cid for s in script.segments for cid in s.claim_ids] or ["no_claim_segments"],
            detail=f"{len(script.segments)} segment(s) after fact-check",
        ),
        CapabilityStatus(
            name="fact_check",
            lifecycle=CapabilityLifecycle.TESTED,
            confidence=Confidence(value=0.5, basis="rule-based verification against the claim ledger's own verification_status"),
            evidence_refs=[r.claim_id for r in fact_check_results] or ["no_claims_checked"],
            detail=f"{len(unsupported_removed)} claim(s) removed as UNSUPPORTED",
        ),
        CapabilityStatus(
            name="voice",
            lifecycle=CapabilityLifecycle.TESTED if render_record else CapabilityLifecycle.NOT_IMPLEMENTED,
            confidence=Confidence(value=0.5, basis="real macOS `say` local TTS, no cloud credentials"),
            evidence_refs=[render_record.output_hash] if render_record else ["no_render"],
            detail="local, credential-free TTS only",
        ),
        CapabilityStatus(
            name="visuals",
            lifecycle=CapabilityLifecycle.TESTED if thumbnail else CapabilityLifecycle.NOT_IMPLEMENTED,
            confidence=Confidence(value=0.5, basis="real Pillow-rendered stills, evidence-text-derived, never misrepresented as documentary footage"),
            evidence_refs=[thumbnail.output_hash] if thumbnail else ["no_visuals"],
            detail="generated stills only",
        ),
        CapabilityStatus(
            name="rights",
            lifecycle=CapabilityLifecycle.TESTED,
            confidence=Confidence(value=0.6, basis="every asset has an explicit rights_status; UNKNOWN assets are excluded, never silently used"),
            evidence_refs=[r.asset_id for r in rights_usable] or ["no_assets"],
            detail=f"{len(rights_usable)} usable, {len(rights_blocked)} blocked",
        ),
        CapabilityStatus(
            name="editing",
            lifecycle=CapabilityLifecycle.TESTED if render_record else CapabilityLifecycle.NOT_IMPLEMENTED,
            confidence=Confidence(value=0.4, basis="minimal real still+audio composition via ffmpeg, not a full non-linear edit"),
            evidence_refs=[render_record.output_hash] if render_record else ["no_render"],
            detail="single still + narration composition, no multi-cut timeline",
        ),
        CapabilityStatus(
            name="render",
            lifecycle=CapabilityLifecycle.TESTED if render_record else CapabilityLifecycle.NOT_IMPLEMENTED,
            confidence=Confidence(value=0.6, basis="real ffmpeg render, real output file, real sha256 hash"),
            evidence_refs=[render_record.output_hash] if render_record else ["no_render"],
            detail=f"duration={render_record.duration_seconds if render_record else 'UNKNOWN'}s" ,
        ),
        CapabilityStatus(
            name="thumbnail",
            lifecycle=CapabilityLifecycle.TESTED if thumbnail else CapabilityLifecycle.NOT_IMPLEMENTED,
            confidence=Confidence(value=0.5, basis="real Pillow-rendered thumbnail image, text obeys the same claim constraints as the script"),
            evidence_refs=[thumbnail.output_hash] if thumbnail else ["no_thumbnail"],
            detail="",
        ),
        CapabilityStatus(
            name="metadata",
            lifecycle=CapabilityLifecycle.TESTED if metadata else CapabilityLifecycle.NOT_IMPLEMENTED,
            confidence=Confidence(value=0.5, basis="generated from script+evidence pack, disclosure notes included"),
            evidence_refs=["metadata_generated"] if metadata else ["no_metadata"],
            detail="",
        ),
        CapabilityStatus(
            name="publication",
            lifecycle=CapabilityLifecycle.NOT_COMMISSIONED,
            confidence=Confidence.unknown(),
            evidence_refs=["publication_authority_not_granted"],
            detail="NOT_AUTHORIZED -- no upload/publish/schedule code path is ever invoked by this institution; authority_ceiling=GENERATE_INTERNAL",
        ),
    ]

    findings = [
        f"OBSERVED: production_mission_id={production_mission_id} reached terminal_state={terminal_state}",
        f"DERIVED: {len(fact_check_results)} claim(s) fact-checked, {len(unsupported_removed)} removed as UNSUPPORTED",
    ]
    if render_record:
        findings.append(f"OBSERVED: real render output_hash={render_record.output_hash[:16]}... duration={render_record.duration_seconds}s")

    limitations = [
        "Render path uses local macOS `say` + Pillow + ffmpeg, a genuinely different and more minimal path than the pre-existing (DaVinci-Resolve-dependent, never-functional-in-this-environment) pipeline -- see YOUTUBE_F8_FORENSIC_REPORT.md.",
        "No paid/cloud generation service was used; voice quality and visual sophistication are correspondingly minimal.",
        "publication remains NOT_COMMISSIONED by design -- this mission never requests or obtains upload authority.",
    ]

    report = build_report(
        institution="youtube_production",
        mission_id=mission_id,
        objective="Produce one real, evidence-bounded candidate video artifact from a real federation synthesis, without ever reaching publication authority",
        operating_state=OperatingState.TESTED,
        capability_statuses=capability_statuses,
        findings=findings,
        evidence_refs=[i for cs in capability_statuses for i in cs.evidence_refs],
        provenance_refs=evidence_pack.specialist_findings_refs,
        limitations=limitations,
        uncertainty=evidence_pack.stale_evidence,
        resources=ResourceUsage(**resource_usage),
        storage=StorageState(**storage_usage),
    )
    return report.model_dump()
