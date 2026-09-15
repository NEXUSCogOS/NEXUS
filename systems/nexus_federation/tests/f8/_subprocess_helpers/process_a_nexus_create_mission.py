#!/usr/bin/env python3
"""Process A (NEXUS side): given a real, already-computed cross-domain
executive synthesis, decide editorial suitability, and if suitable:
(1) construct + persist a real DelegationProposal to youtube_production
    at authority=GENERATE_INTERNAL -- the first delegation this
    federation has ever issued above the ANALYSE ceiling, made possible
    only by this mission's deliberate, documented raise of
    authority/model.py::MAX_GRANTABLE_AUTHORITY_THIS_PHASE.
(2) build + persist a ProductionMissionContract into YouTube's own store.

If NOT suitable, no contract and no delegation are created --
NO_PRODUCTION_ACTION_REQUIRED is recorded and returned, a legitimate
terminal outcome (mission section 23).

Subprocess in the F8 three-process pipeline (mission section 24).
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

FEDERATION_ROOT = str(Path(__file__).resolve().parents[4] / "nexus_federation")
YOUTUBE_ROOT = str(Path(FEDERATION_ROOT).parent / "youtube_production")

for _p in (FEDERATION_ROOT, YOUTUBE_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ingress.contract_registry import bootstrap_federation_registry
from persistence.db import FederationStore
from authority.model import AuthorityLevel
from budget.schema import ResourceBudget
from delegation.schema import DelegationProposal, RiskClass
from delegation.idempotency import compute_idempotency_key

from mission import build_production_mission, assess_editorial_suitability
from storage import YouTubeProductionStore


def run():
    bootstrap_federation_registry()

    store_path = os.environ.get("FEDERATION_STORE_PATH")
    youtube_db_path = os.environ.get("YOUTUBE_DB_PATH")
    if not store_path or not youtube_db_path:
        raise ValueError("FEDERATION_STORE_PATH and YOUTUBE_DB_PATH environment variables required")

    trigger_id = os.environ["TRIGGER_ID"]
    synthesis_id = os.environ["SYNTHESIS_ID"]
    executive_conclusion_class = os.environ["EXECUTIVE_CONCLUSION_CLASS"]
    executive_conclusion = os.environ["EXECUTIVE_CONCLUSION"]
    evidence_refs = json.loads(os.environ.get("EVIDENCE_REFS_JSON", "[]"))
    provenance_refs = json.loads(os.environ.get("PROVENANCE_REFS_JSON", "[]"))
    event_headline = os.environ.get("EVENT_HEADLINE", "federation cross-domain analysis")
    event_keywords = json.loads(os.environ.get("EVENT_KEYWORDS_JSON", "[]"))
    uncertainties = json.loads(os.environ.get("UNCERTAINTIES_JSON", "[]"))
    contradictory_findings = json.loads(os.environ.get("CONTRADICTORY_FINDINGS_JSON", "[]"))

    store = FederationStore(store_path)
    yt_store = YouTubeProductionStore(youtube_db_path)

    suitable, suitability_reason = assess_editorial_suitability(executive_conclusion_class)

    if not suitable:
        result = {
            "pid": os.getpid(),
            "suitable": False,
            "suitability_reason": suitability_reason,
            "production_mission_id": None,
            "terminal_state": "NO_PRODUCTION_ACTION_REQUIRED",
            "delegation_created": False,
        }
        print(json.dumps(result, indent=2))
        return 0

    contract = build_production_mission(
        trigger_id=trigger_id,
        synthesis_id=synthesis_id,
        executive_conclusion_class=executive_conclusion_class,
        executive_conclusion=executive_conclusion,
        evidence_refs=evidence_refs,
        provenance_refs=provenance_refs,
        event_headline=event_headline,
        event_keywords=event_keywords,
        uncertainties=uncertainties,
        contradictory_findings=contradictory_findings,
    )

    # Real DelegationProposal at GENERATE_INTERNAL -- exercises the
    # raised phase ceiling for the first time in this federation.
    proposal_id = str(uuid5(NAMESPACE_URL, f"f8-delegation:{synthesis_id}:youtube_production"))
    mission_id = f"{trigger_id}-mission-y"
    idempotency_key = compute_idempotency_key(
        institution="nexus_federation", cycle_id=synthesis_id,
        capability_name="production_mission", category="youtube_production_generate_internal",
    )
    proposal = DelegationProposal(
        mission_id=mission_id,
        proposal_id=proposal_id,
        recipient="youtube_production",
        objective=contract.editorial_objective,
        reason=suitability_reason,
        evidence_refs=evidence_refs,
        priority=3,
        authority=AuthorityLevel.GENERATE_INTERNAL,
        constraints=[
            "no publication, upload, scheduling, or external posting of any kind",
            "no claim beyond executive_conclusion_class",
        ],
        resource_budget=ResourceBudget(
            cpu_seconds=120.0, memory_bytes=1024 * 1024 * 1024, elapsed_seconds=300.0,
            local_storage_bytes=5 * 1024 * 1024, external_storage_bytes=200 * 1024 * 1024,
            api_cost_usd=0.0, model_tokens=0,
            basis="F8 policy default for a bounded, local-tools-only production mission",
        ),
        risk_class=RiskClass.LOW,
        parent_mission=synthesis_id,
        idempotency_key=idempotency_key,
    )

    composite_key = f"{proposal.mission_id}:{proposal.proposal_id}"
    existing_delegation = store.get_delegation_by_idempotency_key(composite_key)
    delegation_newly_created = existing_delegation is None
    if delegation_newly_created:
        store.record_delegation_proposal(
            delegation_id=proposal.proposal_id,
            mission_id=proposal.mission_id,
            target_institution="youtube_production",
            payload=proposal.model_dump(),
        )

    mission_newly_created = yt_store.upsert_mission(
        contract,
        terminal_state=contract.terminal_state,
        created_at=contract.created_at,
        updated_at=contract.created_at,
    )
    yt_store.increment_counter("missions_received")
    if contract.terminal_state == "NO_APPROPRIATE_CHANNEL":
        yt_store.increment_counter("missions_rejected")
    else:
        yt_store.increment_counter("missions_accepted")

    store.commit()

    result = {
        "pid": os.getpid(),
        "suitable": True,
        "suitability_reason": suitability_reason,
        "production_mission_id": contract.production_mission_id,
        "terminal_state": contract.terminal_state,
        "channel_id": contract.channel_id,
        "delegation_created": delegation_newly_created,
        "delegation_proposal_id": proposal.proposal_id,
        "delegation_authority": proposal.authority.value,
        "mission_newly_created": mission_newly_created,
        "federation_store_path": store_path,
        "youtube_db_path": youtube_db_path,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
