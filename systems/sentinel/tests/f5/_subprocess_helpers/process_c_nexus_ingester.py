#!/usr/bin/env python3
"""Process C: NEXUS ingests Sentinel's result through the federation kernel.

Subprocess 3 of the F5 three-process E2E test. Identical in structure to
F4C's process_c_nexus_ingester.py (Librarian) -- proves the SAME generic
ingress path handles a third institution with zero Sentinel-specific
parsing code.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

federation_root = str(Path(__file__).resolve().parents[4] / "nexus_federation")
sentinel_nexus_root = str(Path(__file__).resolve().parents[3])
dat_ai_root = str(Path(federation_root).parent / "dat_ai")

for _p in (federation_root, sentinel_nexus_root, dat_ai_root):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ingress.contract_registry import bootstrap_federation_registry
from persistence.db import FederationStore
from kernel import FederationKernel


def run():
    bootstrap_federation_registry()

    store_path = os.environ.get("FEDERATION_STORE_PATH")
    mission_id = os.environ.get("MISSION_ID")
    report_id = os.environ.get("REPORT_ID")

    if not all([store_path, mission_id, report_id]):
        raise ValueError("Missing required environment variables: FEDERATION_STORE_PATH, MISSION_ID, REPORT_ID")

    store = FederationStore(store_path)

    report_payload = store.get_institutional_report(report_id)
    if not report_payload:
        raise ValueError(f"Report {report_id} not found in federation store")

    kernel = FederationKernel(store)

    now = datetime.now(timezone.utc)
    ingress_result = kernel.ingest_report(
        raw_payload=report_payload,
        now=now,
        triggering_provenance_ids=[mission_id] if mission_id else [],
    )

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
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
