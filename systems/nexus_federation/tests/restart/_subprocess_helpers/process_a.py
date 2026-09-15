#!/usr/bin/env python3
"""PROCESS A: real subprocess restart-recovery helper.

Ingests one valid DAT.AI report (with a relevance signal, so a delegation
is produced), checkpoints the SQLite store, and prints a single JSON line
to stdout describing what happened -- for tests/restart/test_subprocess_restart.py
to parse. Then exits completely (this whole Python process ends).

Usage: process_a.py <db_path>
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


def main() -> None:
    db_path = sys.argv[1]
    store = FederationStore(db_path)
    kernel = FederationKernel(store)

    ts = datetime.now(timezone.utc).isoformat()
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
    payload["timestamp"] = ts

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
    store.checkpoint()

    print(
        json.dumps(
            {
                "pid": os.getpid(),
                "accepted": result.accepted,
                "temporal_classification": result.temporal_classification,
                "cycle_id": "subprocess-cycle-A",
                "delegation_count": len(result.delegations),
                "total_delegations_in_store": store.count_delegations(),
                "registry_entry": result.registry_entry,
                "evidence_baseline": store.get_evidence_baseline("dat_ai", "DATAI_CANONICAL_TEST_BASELINE.md"),
            }
        )
    )


if __name__ == "__main__":
    main()
