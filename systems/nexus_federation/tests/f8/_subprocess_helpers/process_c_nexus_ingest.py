#!/usr/bin/env python3
"""Process C (NEXUS side): a FRESH process (no in-memory state from
Process A or B survives here) reads YouTube Production's already-
persisted, already-accepted InstitutionalReport back from the SAME
federation store, and records NEXUS's own executive state transition to
READY_FOR_PUBLICATION_AUTHORIZATION -- the only handoff mechanism between
processes is real SQLite persistence, per mission section 24.

Subprocess in the F8 three-process pipeline.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

FEDERATION_ROOT = str(Path(__file__).resolve().parents[4] / "nexus_federation")
YOUTUBE_ROOT = str(Path(FEDERATION_ROOT).parent / "youtube_production")

for _p in (FEDERATION_ROOT, YOUTUBE_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ingress.contract_registry import bootstrap_federation_registry
from persistence.db import FederationStore

from storage import YouTubeProductionStore


def run():
    bootstrap_federation_registry()

    store_path = os.environ.get("FEDERATION_STORE_PATH")
    youtube_db_path = os.environ.get("YOUTUBE_DB_PATH")
    production_mission_id = os.environ.get("PRODUCTION_MISSION_ID")
    if not store_path or not youtube_db_path or not production_mission_id:
        raise ValueError("FEDERATION_STORE_PATH, YOUTUBE_DB_PATH, PRODUCTION_MISSION_ID required")

    store = FederationStore(store_path)
    yt_store = YouTubeProductionStore(youtube_db_path)

    accepted = store.last_accepted_report("youtube_production")
    if accepted is None:
        raise RuntimeError("no accepted youtube_production report found -- run process_b first")

    report = accepted["report"]
    cycle_id = accepted["cycle_id"]

    mission_row = yt_store.find_mission(production_mission_id)
    if mission_row is None:
        raise RuntimeError(f"no mission {production_mission_id} found in YouTube store")

    now = datetime.now(timezone.utc)

    # Idempotent: only append a new state event the first time THIS
    # report cycle_id is seen for this mission (mirrors F6 Process D's
    # own identity-based idempotency).
    identity_prefix = f"identity:{production_mission_id}:"
    already_recorded = any(
        e.get("cycle_id", "").startswith(identity_prefix)
        for e in store.get_state_events("youtube_production", capability_name="production_mission")
    )
    if not already_recorded:
        store.append_state_event(
            institution_id="youtube_production",
            capability_name="production_mission",
            cycle_id=f"identity:{production_mission_id}:{cycle_id}",
            prior_lifecycle=mission_row["terminal_state"],
            new_lifecycle="READY_FOR_PUBLICATION_AUTHORIZATION",
            executive_state_class="DERIVED",
            temporal_classification="PRODUCTION_COMPLETE",
            transition_reason=f"YouTube production report {cycle_id} accepted; publication authority remains NOT_GRANTED",
            evidence_refs=report.get("evidence_refs", []),
            recorded_at=now.isoformat(),
        )

    store.append_observability_event(
        event_type="f8_production_ready_for_authorization",
        detail=json.dumps({
            "production_mission_id": production_mission_id,
            "report_cycle_id": cycle_id,
            "publication_component_state": next(
                (c["lifecycle"] for c in report.get("capability_statuses", []) if c["name"] == "publication"), "UNKNOWN",
            ),
        }),
        recorded_at=now.isoformat(),
    )
    yt_store.set_terminal_state(production_mission_id, "READY_FOR_PUBLICATION_AUTHORIZATION", now.isoformat())
    yt_store.increment_counter("ready_for_authorization_count")
    store.commit()

    result = {
        "pid": os.getpid(),
        "production_mission_id": production_mission_id,
        "report_cycle_id": cycle_id,
        "already_recorded": already_recorded,
        "final_terminal_state": "READY_FOR_PUBLICATION_AUTHORIZATION",
        "publication_component_lifecycle": next(
            (c["lifecycle"] for c in report.get("capability_statuses", []) if c["name"] == "publication"), "UNKNOWN",
        ),
        "federation_store_path": store_path,
        "youtube_db_path": youtube_db_path,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
