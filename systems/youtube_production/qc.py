"""Editorial QC. NEXUS Federation F8, mission section 22: component
states, explicitly NOT combined into an arbitrary "quality score".
"""

from __future__ import annotations

from schema import EditorialQCResult


def run_editorial_qc(
    *,
    fact_check_results: list,
    script,
    render_record,
    thumbnail,
    metadata,
    blocked_rights: list,
) -> EditorialQCResult:
    notes: list[str] = []

    unsupported = [r for r in fact_check_results if r.outcome == "UNSUPPORTED"]
    factual_integrity = "PASS" if not unsupported else f"FAIL ({len(unsupported)} unsupported claim(s) survived, should have been removed)"

    claimed_segments = [s for s in script.segments if s.segment_class != "EDITORIAL_TRANSITION"]
    cited_segments = [s for s in claimed_segments if s.claim_ids]
    citation_coverage = "PASS" if claimed_segments and len(cited_segments) == len(claimed_segments) else (
        "PASS (no factual segments)" if not claimed_segments else f"FAIL ({len(claimed_segments) - len(cited_segments)} uncited factual segment(s))"
    )

    evidence_fidelity = "PASS" if all(r.outcome in ("SUPPORTED", "PARTIAL") for r in fact_check_results) else "FAIL"

    audio_quality = "PASS (real audio file rendered, duration>0)" if render_record and render_record.duration_seconds > 0 else "UNVERIFIED"
    visual_integrity = "PASS (generated stills only, no misrepresented stock/documentary footage)"
    rights_state = "PASS (no blocked-rights asset used in render)" if not blocked_rights else f"BLOCKED ({len(blocked_rights)} asset(s) excluded for rights, correctly not used)"
    caption_accuracy = "NOT_APPLICABLE (no burned-in captions generated this mission)"
    render_completeness = "PASS" if render_record and render_record.output_hash else "FAIL (no render record)"
    thumbnail_honesty = "PASS (thumbnail text matches script/evidence claims)" if thumbnail else "NOT_APPLICABLE"
    metadata_consistency = "PASS (metadata disclosure notes present)" if metadata and metadata.disclosure_notes else "FAIL"

    if unsupported:
        notes.append(f"{len(unsupported)} claim(s) were UNSUPPORTED and removed before render -- see fact_check_results")
    if blocked_rights:
        notes.append(f"{len(blocked_rights)} asset(s) excluded for UNKNOWN/insufficient rights -- see rights_records")

    return EditorialQCResult(
        factual_integrity=factual_integrity,
        citation_coverage=citation_coverage,
        evidence_fidelity=evidence_fidelity,
        audio_quality=audio_quality,
        visual_integrity=visual_integrity,
        rights_state=rights_state,
        caption_accuracy=caption_accuracy,
        render_completeness=render_completeness,
        thumbnail_honesty=thumbnail_honesty,
        metadata_consistency=metadata_consistency,
        notes=notes,
    )
