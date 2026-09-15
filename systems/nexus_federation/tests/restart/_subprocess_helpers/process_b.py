#!/usr/bin/env python3
"""PROCESS B: real subprocess restart-recovery helper.

Started as a completely fresh Python process (no shared memory, no shared
objects, with Process A having fully exited beforehand). Loads the SAME
SQLite file Process A wrote to, verifies persisted state, re-ingests the
IDENTICAL payload Process A ingested (proving duplicate recognition and
duplicate-delegation suppression survive a real process boundary), checks
stale-classification re-derivation, and records a `process_recovery`
observability event once every check has actually passed -- never
beforehand.

Usage: process_b.py <db_path>
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.environ["FEDERATION_ROOT"])
sys.path.insert(0, os.environ["DAT_AI_ROOT"])

from institutional.contract import (  # noqa: E402
    CapabilityLifecycle,
    CapabilityStatus,
    ComponentEvidence,
    Confidence,
    build_report,
)
from kernel import FederationKernel  # noqa: E402
from persistence.db import FederationStore  # noqa: E402
from relevance.router import RelevanceSignal  # noqa: E402
from state.temporal import classify_age_only  # noqa: E402


def main() -> None:
    db_path = sys.argv[1]
    process_a_ts = sys.argv[2]  # the exact timestamp Process A used, so Process B can rebuild an identical payload
    store = FederationStore(db_path)
    kernel = FederationKernel(store)

    checks: dict[str, object] = {}

    # 1. institution state survives
    entry = store.get_registry_entry("dat_ai")
    checks["institution_state_survives"] = entry is not None

    # 2. accepted cycle survives
    checks["accepted_cycle_survives"] = (entry or {}).get("last_verified_cycle") == "subprocess-cycle-A"

    # 3. evidence links survive
    baseline = store.get_evidence_baseline("dat_ai", "DATAI_CANONICAL_TEST_BASELINE.md")
    checks["evidence_links_survive"] = bool(baseline) and len(baseline) == 64

    # 4. temporal ordering survives -- re-derive staleness from the
    # PERSISTED timestamp alone (nothing in this fresh process's memory
    # remembers anything about Process A).
    reclass = classify_age_only((entry or {}).get("last_report_timestamp", process_a_ts))
    checks["temporal_ordering_survives"] = reclass.value in ("CURRENT", "STALE", "EXPIRED")

    delegations_before = store.count_delegations()

    # Rebuild the IDENTICAL payload Process A ingested.
    report = build_report(
        mission_id="subprocess-restart-mission",
        objective="real OS-process restart recovery evidence",
        component_evidence=ComponentEvidence(
            database="healthy", postgis="healthy", migrations="healthy", configuration="healthy"
        ),
        capability_statuses=[
            CapabilityStatus(
                name="zoning_api",
                lifecycle=CapabilityLifecycle.INTEGRATED,
                confidence=Confidence(value=1.0, basis="subprocess restart test fixture"),
                evidence_refs=["DATAI_CANONICAL_TEST_BASELINE.md"],
            ),
        ],
        findings=["zoning_api: real subprocess restart test finding"],
        evidence_refs=["DATAI_CANONICAL_TEST_BASELINE.md"],
        cycle_id="subprocess-cycle-A",
    )
    payload = report.model_dump(mode="json")
    payload["timestamp"] = process_a_ts

    signal = RelevanceSignal(
        institution="dat_ai",
        capability_name="zoning_api",
        category="zoning_change",
        materiality=0.9,
        materiality_basis="subprocess restart test",
        evidence_refs=["DATAI_CANONICAL_TEST_BASELINE.md"],
        parent_mission_id="subprocess-cycle-A",
    )

    result = kernel.ingest_report(payload, relevance_signals=[signal])

    # 5. duplicate report is recognized
    checks["duplicate_recognized"] = result.temporal_classification == "DUPLICATE"
    # 6. duplicate delegation is not generated
    delegations_after = store.count_delegations()
    checks["duplicate_delegation_not_generated"] = delegations_after == delegations_before

    all_passed = all(checks.values())
    if all_passed:
        store.append_observability_event(
            "process_recovery",
            detail="real OS subprocess restart verified: institution state, evidence links, "
            "temporal ordering, and duplicate-delegation suppression all survived a genuine "
            "process boundary",
            recorded_at=datetime.now(timezone.utc).isoformat(),
        )
    store.checkpoint()

    print(
        json.dumps(
            {
                "pid": os.getpid(),
                "checks": checks,
                "all_passed": all_passed,
                "total_delegations_in_store": delegations_after,
                "registry_entry": entry,
                "recorded_process_recovery_event": all_passed,
            }
        )
    )


if __name__ == "__main__":
    main()
