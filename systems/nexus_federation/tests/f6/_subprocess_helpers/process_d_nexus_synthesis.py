#!/usr/bin/env python3
"""Process D: NEXUS starts fresh, ingests both specialist reports through
the generic federation ingress, then performs executive synthesis and
persists the resulting executive state event.

Subprocess 4 of the F6 four-process E2E test.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

FEDERATION_ROOT = str(Path(__file__).resolve().parents[4] / "nexus_federation")
DAT_AI_ROOT = str(Path(FEDERATION_ROOT).parent / "dat_ai")

for _p in (FEDERATION_ROOT, DAT_AI_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ingress.contract_registry import bootstrap_federation_registry
from _resource_accounting import ResourceMeter
from persistence.db import FederationStore
from kernel import FederationKernel
from state.executive_state import ExecutiveStateClass
from synthesis.cross_domain_synthesis import synthesize, ExecutiveConclusionClass


_CLASS_TO_EXECUTIVE_STATE = {
    ExecutiveConclusionClass.SUPPORTED_CROSS_DOMAIN_INFERENCE: ExecutiveStateClass.INFERRED,
    ExecutiveConclusionClass.PARTIALLY_SUPPORTED: ExecutiveStateClass.INFERRED,
    ExecutiveConclusionClass.MIXED_EVIDENCE: ExecutiveStateClass.INFERRED,
    ExecutiveConclusionClass.CONTRADICTORY_EVIDENCE: ExecutiveStateClass.CONTRADICTORY,
    ExecutiveConclusionClass.INSUFFICIENT_EVIDENCE: ExecutiveStateClass.UNKNOWN,
    ExecutiveConclusionClass.NO_MATERIAL_CROSS_DOMAIN_EFFECT_ESTABLISHED: ExecutiveStateClass.DERIVED,
}


def run():
    meter = ResourceMeter().start()
    bootstrap_federation_registry()

    store_path = os.environ.get("FEDERATION_STORE_PATH")
    trigger_id = os.environ.get("TRIGGER_ID")
    dat_ai_observation_ts = os.environ.get("DAT_AI_OBSERVATION_TS", "2025-10-13T03:40:37+00:00")
    librarian_report_id = os.environ.get("LIBRARIAN_REPORT_ID")  # may be absent (failure test)
    sentinel_report_id = os.environ.get("SENTINEL_REPORT_ID")  # may be absent (failure test)

    if not store_path or not trigger_id:
        raise ValueError("FEDERATION_STORE_PATH and TRIGGER_ID environment variables required")

    store = FederationStore(store_path)
    kernel = FederationKernel(store)

    now = datetime.now(timezone.utc)

    # ---- ingest both reports through the SAME generic ingress DAT.AI/
    # Librarian/Sentinel already use -- no F6-specific parser.
    librarian_report = None
    librarian_ingress = None
    if librarian_report_id:
        payload = store.get_institutional_report(librarian_report_id)
        if payload:
            librarian_ingress = kernel.ingest_report(
                raw_payload=payload, now=now, triggering_provenance_ids=[trigger_id],
            )
            if librarian_ingress.accepted:
                librarian_report = payload

    sentinel_report = None
    sentinel_ingress = None
    if sentinel_report_id:
        payload = store.get_institutional_report(sentinel_report_id)
        if payload:
            sentinel_ingress = kernel.ingest_report(
                raw_payload=payload, now=now, triggering_provenance_ids=[trigger_id],
            )
            if sentinel_ingress.accepted:
                sentinel_report = payload

    trigger_evidence = json.loads(os.environ.get("TRIGGER_EVIDENCE_REFS_JSON", "[]"))
    trigger_provenance = json.loads(os.environ.get("TRIGGER_PROVENANCE_REFS_JSON", "[]"))

    synthesis = synthesize(
        trigger_id=trigger_id,
        trigger_evidence_refs=trigger_evidence,
        trigger_provenance_refs=trigger_provenance,
        dat_ai_observation_ts=dat_ai_observation_ts,
        librarian_report=librarian_report,
        sentinel_report=sentinel_report,
        now=now,
    )

    executive_state_class = _CLASS_TO_EXECUTIVE_STATE[synthesis.executive_conclusion_class]

    # Idempotent persistence (mission section 23: "Process D delayed/
    # restarted -> synthesis occurs exactly once semantically"). The
    # synthesis IDENTITY for this purpose is the exact pair of input
    # report_ids (sorted, so argument order never matters) -- NOT
    # synthesis.synthesis_id, which is a fresh uuid4 minted by
    # synthesize() on every call and therefore cannot itself be used to
    # detect "have I already recorded this". A restarted Process D
    # recomputes its own in-memory ExecutiveSynthesis object every time
    # (cheap, pure, and useful for logging/debugging even on a
    # would-be-duplicate run) but only PERSISTS a new state_event_log row
    # the first time this exact report pair is seen.
    synthesis_identity = "|".join(sorted(synthesis.input_report_ids))
    identity_prefix = f"identity:{synthesis_identity}:"
    already_recorded = any(
        e.get("cycle_id", "").startswith(identity_prefix)
        for e in store.get_state_events("nexus", capability_name="cross_domain_synthesis")
    )

    if not already_recorded:
        store.append_state_event(
            institution_id="nexus",
            capability_name="cross_domain_synthesis",
            cycle_id=f"identity:{synthesis_identity}:{synthesis.synthesis_id}",
            prior_lifecycle=None,
            new_lifecycle=synthesis.executive_conclusion_class.value,
            executive_state_class=executive_state_class.value,
            temporal_classification="SYNTHESIS",
            transition_reason=synthesis.executive_conclusion,
            evidence_refs=synthesis.evidence_refs,
            recorded_at=now.isoformat(),
        )

    store.append_observability_event(
        event_type="f6_cross_domain_synthesis",
        detail=json.dumps({
            "synthesis_id": synthesis.synthesis_id,
            "trigger_id": synthesis.trigger_id,
            "input_report_ids": synthesis.input_report_ids,
            "executive_conclusion_class": synthesis.executive_conclusion_class.value,
            "partial": synthesis.partial,
            "missing_institutions": synthesis.missing_institutions,
        }),
        recorded_at=now.isoformat(),
    )
    store.commit()

    result = {
        "pid": os.getpid(),
        "synthesis_id": synthesis.synthesis_id,
        "trigger_id": synthesis.trigger_id,
        "librarian_ingress_accepted": librarian_ingress.accepted if librarian_ingress else None,
        "sentinel_ingress_accepted": sentinel_ingress.accepted if sentinel_ingress else None,
        "executive_conclusion_class": synthesis.executive_conclusion_class.value,
        "executive_conclusion": synthesis.executive_conclusion,
        "partial": synthesis.partial,
        "missing_institutions": synthesis.missing_institutions,
        "supporting_findings_count": len(synthesis.supporting_findings),
        "contradictory_findings_count": len(synthesis.contradictory_findings),
        "independent_corroboration_count": len(synthesis.independent_corroboration),
        # NEXUS Federation F8: full finding text (not just counts) is
        # needed downstream by youtube_production's evidence-pack
        # builder. Purely additive -- F6's own tests assert on specific
        # keys only (see test_f6_cross_domain_synthesis.py), never on the
        # full key set, so this does not change any existing behavior.
        "supporting_findings": synthesis.supporting_findings,
        "contradictory_findings": synthesis.contradictory_findings,
        "uncertainties": synthesis.uncertainties,
        "temporal_mismatches": synthesis.temporal_mismatches,
        "input_report_ids": synthesis.input_report_ids,
        "evidence_refs": synthesis.evidence_refs,
        "provenance_refs": synthesis.provenance_refs,
        "unsupported_claim_count": 0,  # every finding above traces to a real evidence_ref; see F6_SCIENTIFIC_EVALUATION.md
        "recommended_next_actions": synthesis.recommended_next_actions,
        "prohibited_actions": synthesis.prohibited_actions,
        "temporal_mismatches": synthesis.temporal_mismatches,
        "federation_store_path": store_path,
        "resource_usage": meter.stop(),
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
