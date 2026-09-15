#!/usr/bin/env python3
"""PROCESS A: 'NEXUS process' -- ingests a real DAT.AI report, creates a
real delegation to Librarian, persists it, and exits completely.

Usage: process_a_nexus.py <db_path>
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.environ["FEDERATION_ROOT"])
sys.path.insert(0, os.environ["DAT_AI_ROOT"])
sys.path.insert(0, os.environ["LIBRARIAN_ROOT"])

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

    report = build_report(
        mission_id="subprocess-nexus-librarian-mission",
        objective="real OS-process cross-institution recovery evidence",
        component_evidence=ComponentEvidence(
            database="healthy", postgis="healthy", migrations="healthy", configuration="healthy"
        ),
        capability_statuses=[
            CapabilityStatus(
                name="zoning_api",
                lifecycle=CapabilityLifecycle.INTEGRATED,
                confidence=Confidence(value=1.0, basis="subprocess process-recovery test fixture"),
                evidence_refs=["DATAI_CANONICAL_TEST_BASELINE.md"],
            ),
        ],
        findings=["zoning_api: real subprocess cross-institution test finding"],
        evidence_refs=["DATAI_CANONICAL_TEST_BASELINE.md"],
        cycle_id="subprocess-dat-ai-cycle",
    )
    payload = report.model_dump(mode="json")

    signal = RelevanceSignal(
        institution="dat_ai",
        capability_name="zoning_api",
        category="research_request",
        materiality=0.9,
        materiality_basis="ingestion provenance dedup chunk research support for subprocess test",
        evidence_refs=["DATAI_CANONICAL_TEST_BASELINE.md"],
        parent_mission_id="subprocess-dat-ai-cycle",
    )

    result = kernel.ingest_report(payload, relevance_signals=[signal])
    store.checkpoint()

    print(json.dumps({
        "pid": os.getpid(),
        "accepted": result.accepted,
        "delegation_count": len(result.delegations),
        "delegation": result.delegations[0] if result.delegations else None,
    }))


if __name__ == "__main__":
    main()
