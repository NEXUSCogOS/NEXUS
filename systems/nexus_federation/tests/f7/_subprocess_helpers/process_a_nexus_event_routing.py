#!/usr/bin/env python3
"""NEXUS PROCESS A: loads the real News Intelligence report from the
federation store, assesses event-driven relevance deterministically,
and creates + persists delegation(s) to whichever institution(s) are
justified.

Subprocess 2 of the F7 event-driven cognitive loop.
"""

import json
import os
import sys
from pathlib import Path

FEDERATION_ROOT = str(Path(__file__).resolve().parents[4] / "nexus_federation")
DAT_AI_ROOT = str(Path(FEDERATION_ROOT).parent / "dat_ai")

for _p in (FEDERATION_ROOT, DAT_AI_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ingress.contract_registry import bootstrap_federation_registry
from persistence.db import FederationStore
from relevance.news_event_router import assess_event_relevance, build_mission_for_institution


def run():
    bootstrap_federation_registry()

    store_path = os.environ.get("FEDERATION_STORE_PATH")
    event_id = os.environ.get("EVENT_ID")
    event_type = os.environ.get("EVENT_TYPE")
    materiality_score = int(os.environ.get("MATERIALITY_SCORE", "0"))
    locations = json.loads(os.environ.get("LOCATIONS_JSON", "[]"))
    headline = os.environ.get("HEADLINE", "")
    evidence_refs = json.loads(os.environ.get("EVIDENCE_REFS_JSON", "[]"))

    if not store_path or not event_id:
        raise ValueError("FEDERATION_STORE_PATH and EVENT_ID environment variables required")

    store = FederationStore(store_path)

    relevances = assess_event_relevance(
        event_type=event_type, materiality_score=materiality_score,
        locations=locations, resolved_entities=[],
    )

    delegations_created = []
    for rel in relevances:
        if not rel.relevant:
            continue
        if not rel.executable:
            # Honest capability gap (DAT.AI as a recipient): relevance
            # recorded, but no delegation is fabricated for an
            # institution that cannot execute one.
            continue
        proposal = build_mission_for_institution(
            event_id=event_id, event_type=event_type, headline=headline,
            materiality_score=materiality_score, evidence_refs=evidence_refs,
            relevance=rel,
        )
        existing = store.get_delegation_by_idempotency_key(
            f"{proposal.mission_id}:{proposal.proposal_id}"
        )
        if existing:
            delegations_created.append({
                "recipient": rel.institution, "delegation_id": existing["proposal_id"],
                "mission_id": existing["mission_id"], "already_existed": True,
            })
            continue
        store.record_delegation_proposal(
            delegation_id=proposal.proposal_id, mission_id=proposal.mission_id,
            target_institution=rel.institution, payload=proposal.model_dump(),
        )
        delegations_created.append({
            "recipient": rel.institution, "delegation_id": proposal.proposal_id,
            "mission_id": proposal.mission_id, "already_existed": False,
        })

    store.commit()

    result = {
        "pid": os.getpid(),
        "event_id": event_id,
        "relevances": [
            {"institution": r.institution, "relevant": r.relevant, "reason": r.reason, "executable": r.executable}
            for r in relevances
        ],
        "delegations_created": delegations_created,
        "federation_store_path": store_path,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
