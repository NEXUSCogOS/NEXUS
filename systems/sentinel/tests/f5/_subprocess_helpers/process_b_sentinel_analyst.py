#!/usr/bin/env python3
"""Process B: Sentinel claims delegation and executes bounded financial
analysis against its own real, observed database.

Subprocess 2 of the F5 three-process E2E test. Modeled on F4C's
process_b_librarian_researcher.py.

Idempotency (mission section M): the claim itself
(`store.claim_delegation`) is the atomic guard -- it is a real
`INSERT OR IGNORE` against a UNIQUE column (persistence/db.py,
delegation_delivery_log.proposal_id). If this process is invoked twice
for the same delegation_id, the SECOND invocation's claim returns False
and this process exits WITHOUT running the analysis executor a second
time and WITHOUT persisting a second report -- not because of an
in-memory check, but because the database itself refused the second
claim row.
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
from runtime.frontier_analysis_executor import run_bounded_analysis
from contracts.generic import (
    CapabilityLifecycle,
    CapabilityStatus,
    Confidence,
    OperatingState,
    build_report,
)


def run():
    bootstrap_federation_registry()

    store_path = os.environ.get("FEDERATION_STORE_PATH")
    mission_id = os.environ.get("MISSION_ID")
    delegation_id = os.environ.get("DELEGATION_ID")
    db_path = os.environ.get("SENTINEL_DB_PATH")

    if not all([store_path, mission_id, delegation_id, db_path]):
        raise ValueError("Missing required environment variables")

    store = FederationStore(store_path)

    claim_id = str(uuid4())
    claim_time = datetime.now(timezone.utc)

    claimed = store.claim_delegation(
        delegation_id=delegation_id,
        claim_id=claim_id,
        claimed_by="sentinel",
        claimed_at=claim_time.isoformat(),
    )

    if not claimed:
        # Idempotency guard tripped: this delegation was already claimed
        # (by an earlier invocation of this exact process). Do NOT run the
        # analysis executor again and do NOT persist a second report.
        result = {
            "process_b_success": True,
            "pid": os.getpid(),
            "mission_id": mission_id,
            "delegation_id": delegation_id,
            "claim_id": claim_id,
            "already_claimed": True,
            "report_id": None,
            "analysis_executed": False,
        }
        print(json.dumps(result, indent=2))
        return 0

    # ---- Execute real, read-only analysis against verified Sentinel data
    analysis = run_bounded_analysis(db_path=db_path)

    capability_statuses = [
        CapabilityStatus(
            name=c.name,
            lifecycle=CapabilityLifecycle[c.lifecycle],
            confidence=Confidence(value=0.7, basis="Direct SQL query against financial_intelligence.db")
                        if c.lifecycle not in ("NOT_COMMISSIONED", "UNKNOWN")
                        else Confidence.unknown(),
            evidence_refs=c.evidence_refs,
            detail=c.detail,
        )
        for c in analysis.components
    ]

    now = datetime.now(timezone.utc)
    report_id = str(uuid4())

    report = build_report(
        institution="sentinel",
        mission_id=mission_id,
        objective="Execute bounded financial regime analysis mission",
        operating_state=OperatingState.DEGRADED,
        capability_statuses=capability_statuses,
        findings=analysis.findings,
        evidence_refs=analysis.evidence_refs,
        limitations=analysis.limitations,
        provenance_refs=[delegation_id, claim_id, analysis.analysis_run_id],
    )
    # observations, risks, recommended_next_actions are not build_report()
    # kwargs -- set directly (contracts.generic.InstitutionalReport allows
    # them, build_report() just doesn't expose every field as a parameter).
    report.observations = analysis.observations
    report.risks = analysis.risks
    report.recommended_next_actions = analysis.recommended_next_actions

    store.log_institutional_report(
        institution_id="sentinel",
        mission_id=mission_id,
        report_id=report_id,
        payload=report.model_dump(),
    )
    store.commit()

    result = {
        "process_b_success": True,
        "pid": os.getpid(),
        "mission_id": mission_id,
        "delegation_id": delegation_id,
        "claim_id": claim_id,
        "already_claimed": False,
        "report_id": report_id,
        "analysis_run_id": analysis.analysis_run_id,
        "analysis_executed": True,
        "data_status": analysis.data_status,
        "latest_verified_date": analysis.latest_verified_date,
        "age_days": analysis.age_days,
        "regime_age_days": analysis.regime_age_days,
        "current_market_conclusion_permitted": analysis.current_market_conclusion_permitted,
        "current_regime_conclusion_permitted": analysis.current_regime_conclusion_permitted,
        "component_count": len(capability_statuses),
        "federation_store_path": store_path,
        "created_at": now.isoformat(),
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
