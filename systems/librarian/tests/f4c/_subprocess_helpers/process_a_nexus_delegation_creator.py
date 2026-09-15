#!/usr/bin/env python3
"""Process A: NEXUS creates and persists real delegation.

Subprocess 1 of F4C three-process E2E test.
- Loads federation bootstrap
- Creates real NEXUS delegation with Librarian mission
- Persists through federation store
- Outputs JSON evidence to stdout
- Exits with distinct PID
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# ---- Setup sys.path for clean subprocess environment ----

federation_root = str(Path(__file__).resolve().parents[4] / "nexus_federation")
librarian_root = str(Path(__file__).resolve().parents[3])
dat_ai_root = str(Path(federation_root).parent / "dat_ai")

if federation_root not in sys.path:
    sys.path.insert(0, federation_root)
if librarian_root not in sys.path:
    sys.path.insert(0, librarian_root)
if dat_ai_root not in sys.path:
    sys.path.insert(0, dat_ai_root)

# ---- Now safe to import federation/librarian ----

from ingress.contract_registry import bootstrap_federation_registry
from persistence.db import FederationStore
from delegation.schema import DelegationProposal, RiskClass
from budget.schema import ResourceBudget
from authority.model import AuthorityLevel


def run():
    """Process A: Create and persist NEXUS delegation."""

    # Canonical bootstrap ensures all three institutions registered
    bootstrap_federation_registry()

    # Load or create federation store
    store_path = os.environ.get("FEDERATION_STORE_PATH")
    if not store_path:
        raise ValueError("FEDERATION_STORE_PATH environment variable required")

    store = FederationStore(store_path)

    # Generate real identifiers
    mission_id = str(uuid4())
    delegation_id = str(uuid4())
    parent_mission_id = str(uuid4())
    idempotency_key = f"{mission_id}:{delegation_id}"

    # Research question for the delegation
    research_question = (
        "What empirical and theoretical evidence supports separating a global "
        "executive layer from specialist cognitive institutions in distributed "
        "cognitive or agent architectures, and what failure modes or limitations "
        "does the literature identify?"
    )

    # Create resource budget with all required fields
    now = datetime.now(timezone.utc)

    budget = ResourceBudget(
        cpu_seconds=30.0,
        memory_bytes=512 * 1024 * 1024,  # 512 MB
        elapsed_seconds=60.0,
        local_storage_bytes=100 * 1024 * 1024,  # 100 MB
        external_storage_bytes=0,
        api_cost_usd=0.0,
        model_tokens=0,
        basis="F4C test baseline"
    )

    # Create real delegation proposal with all required fields
    delegation = DelegationProposal(
        mission_id=mission_id,
        recipient="librarian",
        objective="Execute academic research mission",
        reason=f"F4C test: {research_question}",
        evidence_refs=[],
        priority=3,
        authority=AuthorityLevel.ANALYSE,
        constraints=[],
        resource_budget=budget,
        ttl_deadline=None,
        success_criteria=["Research executed without fabrication"],
        risk_class=RiskClass.LOW,
        parent_mission=parent_mission_id,
        requested_output_contract="InstitutionalReport v1.0.0",
        created_at=now.isoformat(),
        proposal_id=delegation_id,
        idempotency_key=idempotency_key,
        provenance_id=None
    )

    # Persist delegation through federation store
    # (This writes to the delegation table in SQLite)
    store.record_delegation_proposal(
        delegation_id=delegation_id,
        mission_id=mission_id,
        target_institution="librarian",
        payload=delegation.model_dump()
    )

    # Commit to ensure persistence
    store.commit()

    # Output JSON evidence for the test to verify
    result = {
        "process_a_success": True,
        "pid": os.getpid(),
        "mission_id": mission_id,
        "delegation_id": delegation_id,
        "parent_mission_id": parent_mission_id,
        "research_question": research_question,
        "target_institution": "librarian",
        "federation_store_path": store_path,
        "created_at": now.isoformat(),
        "timestamp": now.isoformat()
    }

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
