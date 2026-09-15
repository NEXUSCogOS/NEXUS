"""Evidence Pack + Claim Ledger construction. NEXUS Federation F8,
mission sections 6-7. This is the factual ceiling for the script: nothing
in script.py may state a claim that is not traceable to an EvidenceItem
here, and nothing may cross a claim-class boundary a source item didn't
already establish.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from schema import EvidenceItem, EvidencePack

# A synthesis's own finding strings follow the "TAG: text" convention
# (see cross_domain_synthesis.py::_bucket) -- reused here, not
# reinvented, to map each institution's own epistemic tag onto this
# mission's five script claim classes.
_TAG_TO_CLAIM_CLASS = {
    "OBSERVED_MARKET_FACT": "FACT",
    "SOURCE_FACT": "FACT",
    "PRIMARY_SOURCE_FACT": "FACT",
    "OBSERVED": "FACT",
    "DERIVED_METRIC": "ANALYSIS",
    "DERIVED_SYNTHESIS": "ANALYSIS",
    "DERIVED": "ANALYSIS",
    "MODEL_ESTIMATE": "INTERPRETATION",
    "SIGNAL": "INTERPRETATION",
    "INFERENCE": "INTERPRETATION",
    "RECOMMENDATION": "HYPOTHESIS",
    "HYPOTHESIS": "HYPOTHESIS",
    "CONTRADICTION": "INTERPRETATION",
    "CONTRADICTORY": "INTERPRETATION",
    "UNKNOWN": "UNVERIFIED",
    "INSUFFICIENT_EVIDENCE": "UNVERIFIED",
}


def _claim_class_for(finding_text: str) -> str:
    leading_tag = finding_text.split(":", 1)[0].strip().upper()
    for tag, cls in _TAG_TO_CLAIM_CLASS.items():
        if leading_tag == tag or leading_tag.startswith(tag):
            return cls
    return "UNVERIFIED"


def build_evidence_pack(
    *,
    production_mission_id: str,
    source_event_ref: str,
    nexus_synthesis_ref: str,
    supporting_findings: list[str],
    contradictory_findings: list[str],
    uncertainties: list[str],
    temporal_mismatches: list[str],
    specialist_report_ids: list[str],
) -> EvidencePack:
    items: list[EvidenceItem] = []
    for i, finding in enumerate(supporting_findings):
        items.append(EvidenceItem(
            evidence_id=f"{production_mission_id}:support:{i}",
            source_institution="specialist_synthesis",
            source_ref=nexus_synthesis_ref,
            claim_text=finding,
            claim_class=_claim_class_for(finding),
        ))
    for i, finding in enumerate(contradictory_findings):
        items.append(EvidenceItem(
            evidence_id=f"{production_mission_id}:contradict:{i}",
            source_institution="specialist_synthesis",
            source_ref=nexus_synthesis_ref,
            claim_text=finding,
            claim_class=_claim_class_for(finding),
            uncertainty="CONTRADICTORY across specialist findings -- both sides preserved, neither discarded",
        ))

    stale_evidence = list(temporal_mismatches)

    return EvidencePack(
        evidence_pack_id=str(uuid5(NAMESPACE_URL, f"f8-evidence-pack:{production_mission_id}")),
        production_mission_id=production_mission_id,
        source_event_ref=source_event_ref,
        nexus_synthesis_ref=nexus_synthesis_ref,
        specialist_findings_refs=specialist_report_ids,
        items=items,
        contradictions=contradictory_findings,
        stale_evidence=stale_evidence,
        prohibited_extrapolations=[
            "no specific numeric market forecast beyond what a FACT/ANALYSIS-class item states",
            "no claim of certainty for anything classed INTERPRETATION or HYPOTHESIS",
        ],
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def build_claim_ledger(evidence_pack: EvidencePack, script) -> list:
    """One ClaimLedgerEntry per script segment that carries a claim_id --
    imported lazily to avoid a hard schema->script coupling at module
    load time."""
    from schema import ClaimLedgerEntry

    evidence_by_id = {e.evidence_id: e for e in evidence_pack.items}
    entries: list[ClaimLedgerEntry] = []
    for seg in script.segments:
        for claim_id in seg.claim_ids:
            ev = evidence_by_id.get(claim_id)
            if ev is None:
                # A claim_id with no backing evidence item is itself a
                # finding, not silently dropped -- REJECTED status,
                # never fabricated evidence_refs.
                entries.append(ClaimLedgerEntry(
                    claim_id=claim_id,
                    script_segment=seg.segment_id,
                    claim_text=seg.text,
                    claim_class=seg.segment_class,
                    evidence_refs=[],
                    provenance_refs=[],
                    verification_status="REJECTED",
                    uncertainty="claim_id referenced in script has no matching EvidencePack item",
                    editorial_transform_status="UNCHANGED_FROM_EVIDENCE",
                ))
                continue
            entries.append(ClaimLedgerEntry(
                claim_id=claim_id,
                script_segment=seg.segment_id,
                claim_text=seg.text,
                claim_class=seg.segment_class,
                evidence_refs=[ev.source_ref],
                provenance_refs=[evidence_pack.nexus_synthesis_ref] if evidence_pack.nexus_synthesis_ref else [],
                verification_status="VERIFIED" if ev.claim_class in ("FACT", "ANALYSIS") else "PARTIAL",
                uncertainty=ev.uncertainty,
                editorial_transform_status="UNCHANGED_FROM_EVIDENCE" if seg.text.strip() == ev.claim_text.strip() else "REWORDED",
            ))
    return entries
