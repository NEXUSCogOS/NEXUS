#!/usr/bin/env python3
"""SENTINEL PROCESS: independently claims the News-triggered delegation
and executes real, read-only financial analysis against Sentinel's own
database. Mirrors F6's process_c_sentinel_analysis.py pattern, driven by
a News Intelligence event instead of a DAT.AI finding.
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

FEDERATION_ROOT = str(Path(__file__).resolve().parents[4] / "nexus_federation")
SENTINEL_NEXUS_ROOT = str(Path(FEDERATION_ROOT).parent / "sentinel")
DAT_AI_ROOT = str(Path(FEDERATION_ROOT).parent / "dat_ai")

for _p in (FEDERATION_ROOT, SENTINEL_NEXUS_ROOT, DAT_AI_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ingress.contract_registry import bootstrap_federation_registry
from persistence.db import FederationStore
from contracts.generic import (
    CapabilityLifecycle, CapabilityStatus, Confidence, OperatingState, build_report,
)

SENTINEL_DB_DEFAULT = str(Path(SENTINEL_NEXUS_ROOT) / "financial_intelligence.db")

# Real, well-known Vietnamese industrial-park/land-bank operators (same
# candidate set used in F6, for the same reason: real public knowledge
# that Vietnam's ongoing FDI electronics manufacturing buildout has
# historically driven demand for industrial park land, checked against
# Sentinel's own governed sector data, never assumed).
CANDIDATE_TICKERS = ["KBC", "SZC", "GVR", "IDC", "LHG"]


def run():
    bootstrap_federation_registry()

    store_path = os.environ.get("FEDERATION_STORE_PATH")
    mission_id = os.environ.get("MISSION_ID")
    delegation_id = os.environ.get("DELEGATION_ID")
    db_path = os.environ.get("SENTINEL_DB_PATH", SENTINEL_DB_DEFAULT)
    news_headline = os.environ.get("NEWS_HEADLINE", "")
    news_locations = json.loads(os.environ.get("NEWS_LOCATIONS_JSON", "[]"))
    if not all([store_path, mission_id, delegation_id]):
        raise ValueError("Missing required environment variables")

    store = FederationStore(store_path)
    claim_id = str(uuid4())
    claimed = store.claim_delegation(
        delegation_id=delegation_id, claim_id=claim_id, claimed_by="sentinel",
        claimed_at=datetime.now(timezone.utc).isoformat(),
    )
    if not claimed:
        print(json.dumps({"pid": os.getpid(), "already_claimed": True, "report_id": None}, indent=2))
        return 0

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    observations, findings, limitations, risks, evidence_refs = [], [], [], [], []
    entity_mappings = []

    for ticker in CANDIDATE_TICKERS:
        row = conn.execute("SELECT symbol, sector, full_name FROM companies WHERE symbol=?", (ticker,)).fetchone()
        if row is None:
            classification, basis = "UNKNOWN", f"{ticker} has no row in Sentinel's own companies table"
        elif row["sector"] and "bất động sản" in row["sector"].lower():
            classification = "INDIRECT"
            basis = (
                f"Sentinel's own companies table discloses sector={row['sector']!r} "
                f"(real estate/industrial park) for {ticker} ({row['full_name']}) -- "
                f"plausible general exposure to continued Vietnamese FDI "
                f"electronics manufacturing buildout (of which this news event is "
                f"one data point), NOT confirmed exposure to the specific "
                f"facilities named in this event ({news_locations}); Sentinel's "
                f"data has no facility-level geography."
            )
        else:
            classification = "HYPOTHETICAL"
            basis = f"Sentinel's own companies table discloses sector={row['sector']!r} for {ticker} -- not real-estate-sector-classified; any link is a hypothesis."
        entity_mappings.append({"ticker": ticker, "classification": classification, "basis": basis})
        findings.append(f"DERIVED_METRIC: entity mapping for {ticker} classified {classification} -- {basis}")
        evidence_refs.append(f"companies:symbol={ticker}")

        price_row = conn.execute(
            "SELECT date, close FROM prices_daily WHERE symbol=? AND date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' ORDER BY date DESC LIMIT 1",
            (ticker,),
        ).fetchone()
        if price_row:
            observations.append(f"OBSERVED_MARKET_FACT: {ticker} latest verified close is {price_row['close']} on {price_row['date']}")
            evidence_refs.append(f"prices_daily:symbol={ticker}:date={price_row['date']}")

    limitations.append(
        f"News event locations {news_locations} could not be matched against any "
        f"Sentinel-governed facility-level data -- no company below reaches DIRECT "
        f"classification."
    )
    limitations.append("Neither Sentinel's decision_engine nor regime_detection outputs are historically validated -- see SENTINEL_DECISION_ENGINE_AUDIT.md / SENTINEL_REGIME_ENGINE_AUDIT.md.")
    risks.append("RISK: no forecast is available (Sentinel has no forecasting capability, NOT_COMMISSIONED).")

    conn.close()

    report = build_report(
        institution="sentinel", mission_id=mission_id,
        objective=f"Assess plausible financial exposure to news event: {news_headline}",
        operating_state=OperatingState.INTEGRATED,
        capability_statuses=[
            CapabilityStatus(
                name="news_driven_entity_mapping", lifecycle=CapabilityLifecycle.TESTED,
                confidence=Confidence(value=0.4, basis=f"{len(entity_mappings)} candidate tickers checked; 0 reached DIRECT"),
                evidence_refs=[f"companies:symbol={m['ticker']}" for m in entity_mappings],
                detail=json.dumps(entity_mappings),
            ),
        ],
        findings=findings, evidence_refs=evidence_refs, limitations=limitations,
        provenance_refs=[delegation_id, claim_id],
    )
    report.observations = observations
    report.risks = risks
    report.recommended_next_actions = ["continue monitoring for facility-level disclosure"]

    report_id = str(uuid4())
    store.log_institutional_report(
        institution_id="sentinel", mission_id=mission_id, report_id=report_id,
        payload=report.model_dump(),
    )
    store.commit()

    conn2 = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    exec_pairs = [tuple(r) for r in conn2.execute("SELECT DISTINCT execution_mode, execution_allowed FROM frontier_decisions")]
    conn2.close()

    print(json.dumps({
        "pid": os.getpid(), "already_claimed": False, "mission_id": mission_id,
        "delegation_id": delegation_id, "claim_id": claim_id, "report_id": report_id,
        "entity_mappings": entity_mappings, "exec_pairs_decisions": exec_pairs,
        "federation_store_path": store_path,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
