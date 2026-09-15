#!/usr/bin/env python3
"""Live-execution authority rejection (mission section K).

Attempts to construct (NOT merely propose in free text, but actually
request via the typed `authority` field) a delegation asking Sentinel to
place a live order. "Place a live order" is inherently a
HIGH_CONSEQUENCE_ACTION under authority/model.py's ladder -- there is no
lower authority level that legitimately describes it. The federation's
own AuthorityLevel ladder (authority/model.py) caps
MAX_GRANTABLE_AUTHORITY_THIS_PHASE at ANALYSE; DelegationProposal's own
`_authority_never_exceeds_phase_ceiling` validator raises before the
object can even be constructed.

This script never calls store.record_delegation_proposal() for the
rejected attempt -- rejection happens at object-construction time, before
persistence, before Process B (Sentinel) would ever be invoked, so
Sentinel's analysis code never runs for this request at all.
"""

import json
import os
import sys
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
from pydantic import ValidationError


def run():
    bootstrap_federation_registry()

    store_path = os.environ.get("FEDERATION_STORE_PATH")
    if not store_path:
        raise ValueError("FEDERATION_STORE_PATH environment variable required")

    store = FederationStore(store_path)
    delegations_before = store.count_delegations()

    mission_id = str(uuid4())
    delegation_id = str(uuid4())

    budget = ResourceBudget(
        cpu_seconds=30.0,
        memory_bytes=512 * 1024 * 1024,
        elapsed_seconds=60.0,
        local_storage_bytes=100 * 1024 * 1024,
        external_storage_bytes=0,
        api_cost_usd=0.0,
        model_tokens=0,
        basis="F5 rejection test",
    )

    rejected = False
    rejection_reason = None

    try:
        # This construction is expected to raise -- HIGH_CONSEQUENCE_ACTION
        # exceeds MAX_GRANTABLE_AUTHORITY_THIS_PHASE (ANALYSE).
        delegation = DelegationProposal(
            mission_id=mission_id,
            recipient="sentinel",
            objective="Place a live order for VNM using Sentinel's execution interface",
            reason="F5 negative control: live execution must be rejected before any code runs",
            evidence_refs=[],
            priority=1,
            authority=AuthorityLevel.HIGH_CONSEQUENCE_ACTION,
            constraints=[],
            resource_budget=budget,
            ttl_deadline=None,
            success_criteria=["Order placed"],
            risk_class=RiskClass.HIGH,
            parent_mission=mission_id,
            requested_output_contract="InstitutionalReport v1.0.0",
            proposal_id=delegation_id,
            idempotency_key=f"{mission_id}:{delegation_id}",
            provenance_id=None,
        )
        # If we reach here, construction did NOT raise -- this would be a
        # serious finding (the ceiling did not hold). Do NOT persist it
        # either way; record what happened for the test to fail loudly on.
        rejection_reason = "NOT_REJECTED: DelegationProposal construction succeeded"
    except ValidationError as exc:
        rejected = True
        rejection_reason = str(exc)

    delegations_after = store.count_delegations()

    result = {
        "pid": os.getpid(),
        "authority_rejected": rejected,
        "rejection_reason": rejection_reason,
        "delegations_before": delegations_before,
        "delegations_after": delegations_after,
        "delegation_count_unchanged": delegations_before == delegations_after,
        "mission_id": mission_id,
        "delegation_id": delegation_id,
        "federation_store_path": store_path,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
