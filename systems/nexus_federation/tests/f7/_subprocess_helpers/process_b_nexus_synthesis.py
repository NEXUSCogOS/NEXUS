#!/usr/bin/env python3
"""NEXUS PROCESS B: starts fresh, ingests specialist report(s) through
generic ingress, performs executive synthesis, persists resulting
executive state. Reuses F6's synthesis.cross_domain_synthesis engine --
F7's synthesis need (combine 0-2 specialist reports into one executive
conclusion, preserving claim classes, never concatenating) is
functionally identical to F6's; this is deliberate reuse, not
duplication.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

FEDERATION_ROOT = str(Path(__file__).resolve().parents[4] / "nexus_federation")
DAT_AI_ROOT = str(Path(FEDERATION_ROOT).parent / "dat_ai")

for _p in (FEDERATION_ROOT, DAT_AI_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ingress.contract_registry import bootstrap_federation_registry
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
    bootstrap_federation_registry()

    store_path = os.environ.get("FEDERATION_STORE_PATH")
    trigger_id = os.environ.get("EVENT_ID")
    event_pub_time = os.environ.get("EVENT_PUBLICATION_TIME", datetime.now(timezone.utc).isoformat())
    librarian_report_id = os.environ.get("LIBRARIAN_REPORT_ID")
    sentinel_report_id = os.environ.get("SENTINEL_REPORT_ID")
    expected_institutions = json.loads(os.environ.get("EXPECTED_INSTITUTIONS_JSON", '["librarian", "sentinel"]'))
    if not store_path or not trigger_id:
        raise ValueError("FEDERATION_STORE_PATH and EVENT_ID environment variables required")

    store = FederationStore(store_path)
    kernel = FederationKernel(store)
    now = datetime.now(timezone.utc)

    librarian_report, librarian_ingress = None, None
    if librarian_report_id:
        payload = store.get_institutional_report(librarian_report_id)
        if payload:
            librarian_ingress = kernel.ingest_report(raw_payload=payload, now=now, triggering_provenance_ids=[trigger_id])
            if librarian_ingress.accepted:
                librarian_report = payload

    sentinel_report, sentinel_ingress = None, None
    if sentinel_report_id:
        payload = store.get_institutional_report(sentinel_report_id)
        if payload:
            sentinel_ingress = kernel.ingest_report(raw_payload=payload, now=now, triggering_provenance_ids=[trigger_id])
            if sentinel_ingress.accepted:
                sentinel_report = payload

    trigger_evidence = json.loads(os.environ.get("TRIGGER_EVIDENCE_REFS_JSON", "[]"))
    trigger_provenance = json.loads(os.environ.get("TRIGGER_PROVENANCE_REFS_JSON", "[]"))

    synthesis = synthesize(
        trigger_id=trigger_id, trigger_evidence_refs=trigger_evidence,
        trigger_provenance_refs=trigger_provenance, dat_ai_observation_ts=event_pub_time,
        librarian_report=librarian_report, sentinel_report=sentinel_report, now=now,
        expected_institutions=expected_institutions,
    )

    executive_state_class = _CLASS_TO_EXECUTIVE_STATE[synthesis.executive_conclusion_class]

    synthesis_identity = "|".join(sorted(synthesis.input_report_ids)) if synthesis.input_report_ids else f"trigger:{trigger_id}"
    identity_prefix = f"identity:{synthesis_identity}:"
    already_recorded = any(
        e.get("cycle_id", "").startswith(identity_prefix)
        for e in store.get_state_events("nexus", capability_name="news_event_synthesis")
    )
    if not already_recorded:
        store.append_state_event(
            institution_id="nexus", capability_name="news_event_synthesis",
            cycle_id=f"identity:{synthesis_identity}:{synthesis.synthesis_id}",
            prior_lifecycle=None, new_lifecycle=synthesis.executive_conclusion_class.value,
            executive_state_class=executive_state_class.value, temporal_classification="SYNTHESIS",
            transition_reason=synthesis.executive_conclusion, evidence_refs=synthesis.evidence_refs,
            recorded_at=now.isoformat(),
        )

    store.append_observability_event(
        event_type="f7_news_event_synthesis",
        detail=json.dumps({
            "synthesis_id": synthesis.synthesis_id, "trigger_id": synthesis.trigger_id,
            "input_report_ids": synthesis.input_report_ids,
            "executive_conclusion_class": synthesis.executive_conclusion_class.value,
            "partial": synthesis.partial, "missing_institutions": synthesis.missing_institutions,
        }),
        recorded_at=now.isoformat(),
    )
    store.commit()

    print(json.dumps({
        "pid": os.getpid(), "synthesis_id": synthesis.synthesis_id, "trigger_id": synthesis.trigger_id,
        "librarian_ingress_accepted": librarian_ingress.accepted if librarian_ingress else None,
        "sentinel_ingress_accepted": sentinel_ingress.accepted if sentinel_ingress else None,
        "executive_conclusion_class": synthesis.executive_conclusion_class.value,
        "executive_conclusion": synthesis.executive_conclusion,
        "partial": synthesis.partial, "missing_institutions": synthesis.missing_institutions,
        "recommended_next_actions": synthesis.recommended_next_actions,
        "prohibited_actions": synthesis.prohibited_actions,
        "federation_store_path": store_path,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
