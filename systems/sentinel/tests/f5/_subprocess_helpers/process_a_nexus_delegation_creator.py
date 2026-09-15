#!/usr/bin/env python3
"""Process A: NEXUS creates and persists a real Sentinel delegation.

Subprocess 1 of the F5 three-process E2E test. Modeled directly on F4C's
process_a_nexus_delegation_creator.py (Librarian), substituting Sentinel
as recipient and a mission that remains valid even with stale downstream
data (see SENTINEL_INSTITUTIONAL_CONTRACT.md, mission section I).
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

federation_root = str(Path(__file__).resolve().parents[4] / "nexus_federation")
sentinel_nexus_root = str(Path(__file__).resolve().parents[3])
dat_ai_root = str(Path(federation_root).parent / "dat_ai")

for _p in (federation_root, sentinel_nexus_root, dat_ai_root):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ingress.contract_registry import bootstrap_federation_registry
from persistence.db import FederationStore
from delegation.schema import DelegationProposal, RiskClass
from budget.schema import ResourceBudget
from authority.model import AuthorityLevel

MISSION_OBJECTIVE = (
    "Using the latest verified Sentinel data available, characterize the "
    "most recent supported market regime, identify major analytical risks "
    "and data limitations, and distinguish clearly between observed facts, "
    "derived metrics, model estimates, forecasts, signals, and "
    "recommendations. Do not perform any live financial execution."
)


def run():
    bootstrap_federation_registry()

    store_path = os.environ.get("FEDERATION_STORE_PATH")
    if not store_path:
        raise ValueError("FEDERATION_STORE_PATH environment variable required")

    store = FederationStore(store_path)

    mission_id = str(uuid4())
    delegation_id = str(uuid4())
    parent_mission_id = str(uuid4())
    idempotency_key = f"{mission_id}:{delegation_id}"

    now = datetime.now(timezone.utc)

    budget = ResourceBudget(
        cpu_seconds=30.0,
        memory_bytes=512 * 1024 * 1024,
        elapsed_seconds=60.0,
        local_storage_bytes=100 * 1024 * 1024,
        external_storage_bytes=0,
        api_cost_usd=0.0,
        model_tokens=0,
        basis="F5 test baseline",
    )

    delegation = DelegationProposal(
        mission_id=mission_id,
        recipient="sentinel",
        objective=MISSION_OBJECTIVE,
        reason="F5 commissioning mission: bounded financial regime analysis",
        evidence_refs=[],
        priority=3,
        authority=AuthorityLevel.ANALYSE,
        constraints=[
            "no live execution",
            "no fabrication of current data from stale sources",
        ],
        resource_budget=budget,
        ttl_deadline=None,
        success_criteria=[
            "Analysis executed against verified Sentinel data only",
            "Epistemology distinctions present in the report",
        ],
        risk_class=RiskClass.LOW,
        parent_mission=parent_mission_id,
        requested_output_contract="InstitutionalReport v1.0.0",
        created_at=now.isoformat(),
        proposal_id=delegation_id,
        idempotency_key=idempotency_key,
        provenance_id=None,
    )

    store.record_delegation_proposal(
        delegation_id=delegation_id,
        mission_id=mission_id,
        target_institution="sentinel",
        payload=delegation.model_dump(),
    )
    store.commit()

    result = {
        "process_a_success": True,
        "pid": os.getpid(),
        "mission_id": mission_id,
        "delegation_id": delegation_id,
        "parent_mission_id": parent_mission_id,
        "objective": MISSION_OBJECTIVE,
        "target_institution": "sentinel",
        "federation_store_path": store_path,
        "created_at": now.isoformat(),
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
