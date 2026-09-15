#!/usr/bin/env python3
"""Process C: NEXUS ingests Librarian result through federation.

Subprocess 3 of F4C three-process E2E test.
- Loads federation bootstrap
- Discovers persisted Librarian report in store
- Ingests through federation kernel using generic contract
- Validates and updates executive state
- Outputs JSON evidence to stdout
- Exits with distinct PID
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

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
from kernel import FederationKernel


def run():
    """Process C: Ingest Librarian report through federation kernel."""

    # Canonical bootstrap ensures all three institutions registered
    bootstrap_federation_registry()

    # Get inputs from environment
    store_path = os.environ.get("FEDERATION_STORE_PATH")
    mission_id = os.environ.get("MISSION_ID")
    report_id = os.environ.get("REPORT_ID")

    if not all([store_path, mission_id, report_id]):
        raise ValueError("Missing required environment variables: FEDERATION_STORE_PATH, MISSION_ID, REPORT_ID")

    # Load federation store
    store = FederationStore(store_path)

    # Retrieve the persisted Librarian report
    report_payload = store.get_institutional_report(report_id)
    if not report_payload:
        raise ValueError(f"Report {report_id} not found in federation store")

    # Create federation kernel
    kernel = FederationKernel(store)

    # Ingest report through kernel
    # This validates the contract, updates registry, and creates provenance
    now = datetime.now(timezone.utc)
    ingress_result = kernel.ingest_report(
        raw_payload=report_payload,
        now=now,
        triggering_provenance_ids=[mission_id] if mission_id else []
    )

    # Output JSON evidence for the test to verify
    result = {
        "process_c_success": True,
        "pid": os.getpid(),
        "report_id": report_id,
        "mission_id": mission_id,
        "ingress_accepted": ingress_result.accepted,
        "ingress_reason": ingress_result.reason,
        "temporal_classification": ingress_result.temporal_classification,
        "registry_entry_created": ingress_result.registry_entry is not None,
        "delegations_created": len(ingress_result.delegations),
        "provenance_ids": ingress_result.provenance_ids,
        "evidence_resolution_failures": ingress_result.evidence_resolution_failures,
        "federation_store_path": store_path,
        "created_at": now.isoformat(),
        "timestamp": now.isoformat()
    }

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
