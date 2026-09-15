#!/usr/bin/env python3
"""Process A: NEXUS loads the real DAT.AI trigger, assesses cross-domain
relevance deterministically, and creates + persists two independent
delegations (Librarian, Sentinel).

Subprocess 1 of the F6 four-process E2E test.
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

FEDERATION_ROOT = str(Path(__file__).resolve().parents[4] / "nexus_federation")
DAT_AI_ROOT = str(Path(FEDERATION_ROOT).parent / "dat_ai")

for _p in (FEDERATION_ROOT, DAT_AI_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ingress.contract_registry import bootstrap_federation_registry
from _resource_accounting import ResourceMeter
from persistence.db import FederationStore
from relevance.cross_domain_router import (
    CrossDomainTrigger,
    assess_attention,
    assess_cross_domain_relevance,
    build_mission_l_librarian,
    build_mission_s_sentinel,
)


def _derive_candidate_implications(dat_ai_report: dict) -> list[str]:
    """Deterministic keyword detection against the DAT.AI report's OWN
    text fields -- never a hand-picked tag list. 'candidate_implications
    are hypotheses for routing, not facts' (mission section 3): this
    function only proposes routing hypotheses grounded in what DAT.AI's
    own report actually said, via a fixed, inspectable keyword table."""

    text = " ".join(
        dat_ai_report.get("findings", [])
        + dat_ai_report.get("cross_system_implications", [])
    ).lower()

    tags = []
    if any(k in text for k in ("government", "planning", "quy hoạch", "construction plan", "official")):
        tags.append("policy")
    if any(k in text for k in ("industrial", "logistics", "development pressure", "real-estate", "real estate", "economic")):
        tags.append("economic")
    if any(k in text for k in ("sector", "exposed", "exposure", "listed company", "companies")):
        tags.append("sector")
    return tags


def run():
    meter = ResourceMeter().start()
    bootstrap_federation_registry()

    store_path = os.environ.get("FEDERATION_STORE_PATH")
    if not store_path:
        raise ValueError("FEDERATION_STORE_PATH environment variable required")
    store = FederationStore(store_path)

    dat_ai_accepted = store.last_accepted_report("dat_ai")
    if dat_ai_accepted is None:
        raise RuntimeError("No accepted DAT.AI report found -- run process_dat_ai_trigger_source.py first")

    dat_ai_report = dat_ai_accepted["report"]
    dat_ai_cycle_id = dat_ai_accepted["cycle_id"]

    override_geography = os.environ.get("F6_TRIGGER_GEOGRAPHY_OVERRIDE")
    override_implications = os.environ.get("F6_TRIGGER_IMPLICATIONS_OVERRIDE")

    zone_project_id = os.environ.get("F6_ZONE_PROJECT_ID", "camduong")
    zone_admin_code = os.environ.get("F6_ZONE_ADMIN_CODE", "26401")

    candidate_implications = (
        json.loads(override_implications)
        if override_implications is not None
        else _derive_candidate_implications(dat_ai_report)
    )

    # Deterministic (UUID5), not random -- a replay against the SAME
    # underlying DAT.AI evidence (same source_report_id + same
    # source_finding_id) must reproduce the SAME trigger_id, so the
    # delegations built from it reproduce the SAME idempotency_key and
    # the duplicate-check below (get_delegation_by_idempotency_key) can
    # actually catch a replay (mission section 23).
    trigger_id = str(uuid5(NAMESPACE_URL, f"f6-trigger:{dat_ai_cycle_id}:{zone_project_id}"))

    trigger = CrossDomainTrigger(
        trigger_id=trigger_id,
        source_institution="dat_ai",
        source_report_id=dat_ai_cycle_id,
        source_finding_id=zone_project_id,
        observation_timestamp="2025-10-13T03:40:37+00:00",  # real: PlanningZone.updatedDate for camduong
        received_timestamp=datetime.now(timezone.utc).isoformat(),
        evidence_refs=list(dat_ai_report.get("evidence_refs", [])),
        provenance_refs=list(dat_ai_report.get("provenance_refs", [])) or [dat_ai_cycle_id],
        claim_class="OBSERVED",
        geography=override_geography or "Long Thanh district, Dong Nai province, Vietnam",
        materiality=float(os.environ.get("F6_TRIGGER_MATERIALITY", "0.65")),
        materiality_basis=(
            "general construction plan geometrically adjacent "
            "(shapely-computed ~1.2km boundary distance) to Long Thanh "
            "International Airport, a nationally significant "
            "infrastructure project under construction"
        ),
        uncertainty=list(dat_ai_report.get("uncertainty", [])),
        limitations=list(dat_ai_report.get("limitations", [])),
        freshness="STALE_BUT_USABLE_AS_HISTORICAL_CONTEXT",
        candidate_implications=candidate_implications,
    )

    relevances = assess_cross_domain_relevance(trigger)
    lib_rel = next(r for r in relevances if r.institution == "librarian")
    sen_rel = next(r for r in relevances if r.institution == "sentinel")

    attention = assess_attention(trigger, relevances)

    delegations_created = []

    def _persist_or_reuse(build_fn, relevance, recipient):
        """Mission section 23: same trigger replay -> no duplicate
        specialist mission. Both `mission_id` and `proposal_id` are now
        fully deterministic (derived from trigger_id, itself
        deterministic -- see above). `record_delegation_proposal`
        (persistence/db.py) computes its OWN idempotency key internally
        as `f"{mission_id}:{delegation_id}"` -- NOT the DelegationProposal
        schema's own `idempotency_key` field (a real, pre-existing
        divergence between the two idempotency notions in this codebase,
        found while building this check) -- so the duplicate check below
        must query using that same composite shape, not
        `provisional.idempotency_key`, or it will never find a match."""
        provisional = build_fn(trigger, relevance)
        composite_key = f"{provisional.mission_id}:{provisional.proposal_id}"
        existing = store.get_delegation_by_idempotency_key(composite_key)
        if existing:
            return {
                "recipient": recipient,
                "delegation_id": existing["proposal_id"],
                "mission_id": existing["mission_id"],
                "already_existed": True,
            }
        store.record_delegation_proposal(
            delegation_id=provisional.proposal_id,
            mission_id=provisional.mission_id,
            target_institution=recipient,
            payload=provisional.model_dump(),
        )
        return {
            "recipient": recipient,
            "delegation_id": provisional.proposal_id,
            "mission_id": provisional.mission_id,
            "already_existed": False,
        }

    if lib_rel.relevant:
        delegations_created.append(_persist_or_reuse(build_mission_l_librarian, lib_rel, "librarian"))

    if sen_rel.relevant:
        delegations_created.append(_persist_or_reuse(build_mission_s_sentinel, sen_rel, "sentinel"))

    store.commit()

    result = {
        "pid": os.getpid(),
        "trigger_id": trigger.trigger_id,
        "source_report_id": trigger.source_report_id,
        "source_finding_id": trigger.source_finding_id,
        "geography": trigger.geography,
        "materiality": trigger.materiality,
        "candidate_implications": trigger.candidate_implications,
        "librarian_relevance": {"relevant": lib_rel.relevant, "reason": lib_rel.reason},
        "sentinel_relevance": {"relevant": sen_rel.relevant, "reason": sen_rel.reason},
        "attention": {
            "total_score": attention.total_score,
            "requires_attention": attention.requires_attention,
            "basis": attention.basis,
        },
        "delegations_created": delegations_created,
        "federation_store_path": store_path,
        "resource_usage": meter.stop(),
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
