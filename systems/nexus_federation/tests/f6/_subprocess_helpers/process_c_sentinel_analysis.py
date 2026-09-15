#!/usr/bin/env python3
"""Process C: Sentinel independently claims MISSION S and executes
real, read-only financial analysis against its own real database.

Subprocess 3 of the F6 four-process E2E test. Runs with NO knowledge of
Librarian's mission or result (independence requirement, mission section
6) -- this process never imports or touches anything Librarian-related.

Entity/sector mapping (mission section 11): candidate tickers were
selected from real public knowledge of major Vietnamese industrial-park/
land-bank operators (not from Sentinel's data), then EVERY mapping below
is classified DIRECT/INDIRECT/HYPOTHETICAL/UNKNOWN strictly against what
Sentinel's OWN governed `companies` table actually discloses -- never
from the ticker name alone (mission's explicit prohibition). No company
here has Sentinel-disclosed text confirming a specific Dong Nai/Long
Thanh facility, so DIRECT is never reached by any of them.
"""

import json
import os
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

FEDERATION_ROOT = str(Path(__file__).resolve().parents[4] / "nexus_federation")
SENTINEL_NEXUS_ROOT = str(Path(FEDERATION_ROOT).parent / "sentinel")
DAT_AI_ROOT = str(Path(FEDERATION_ROOT).parent / "dat_ai")

for _p in (FEDERATION_ROOT, SENTINEL_NEXUS_ROOT, DAT_AI_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ingress.contract_registry import bootstrap_federation_registry
from _resource_accounting import ResourceMeter
from persistence.db import FederationStore
from contracts.generic import (
    CapabilityLifecycle,
    CapabilityStatus,
    Confidence,
    OperatingState,
    build_report,
)

SENTINEL_DB_DEFAULT = str(Path(SENTINEL_NEXUS_ROOT) / "financial_intelligence.db")

# Candidate tickers: real, well-known Vietnamese industrial-park/land-bank
# operators (public knowledge, not Sentinel-sourced). Only tickers present
# in Sentinel's own real universe are checked.
CANDIDATE_TICKERS = ["KBC", "SZC", "GVR", "IDC", "LHG"]


def run():
    meter = ResourceMeter().start()
    bootstrap_federation_registry()

    store_path = os.environ.get("FEDERATION_STORE_PATH")
    mission_id = os.environ.get("MISSION_ID")
    delegation_id = os.environ.get("DELEGATION_ID")
    db_path = os.environ.get("SENTINEL_DB_PATH", SENTINEL_DB_DEFAULT)
    if not all([store_path, mission_id, delegation_id]):
        raise ValueError("Missing required environment variables")

    store = FederationStore(store_path)

    claim_id = str(uuid4())
    claimed = store.claim_delegation(
        delegation_id=delegation_id,
        claim_id=claim_id,
        claimed_by="sentinel",
        claimed_at=datetime.now(timezone.utc).isoformat(),
    )
    if not claimed:
        result = {"pid": os.getpid(), "already_claimed": True, "report_id": None, "resource_usage": meter.stop()}
        print(json.dumps(result, indent=2))
        return 0

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    observations = []
    findings = []
    limitations = []
    risks = []
    evidence_refs = []
    entity_mappings = []

    for ticker in CANDIDATE_TICKERS:
        company_row = conn.execute(
            "SELECT symbol, sector, full_name FROM companies WHERE symbol=?", (ticker,)
        ).fetchone()

        if company_row is None:
            classification = "UNKNOWN"
            basis = (
                f"{ticker} has no row in Sentinel's own `companies` table "
                f"-- no sector/name data governed by Sentinel exists for "
                f"it, despite being a real, publicly known industrial-"
                f"park-adjacent operator. Cannot classify beyond UNKNOWN "
                f"from Sentinel's own data."
            )
        elif company_row["sector"] and "bất động sản" in company_row["sector"].lower():
            classification = "INDIRECT"
            basis = (
                f"Sentinel's own `companies` table discloses sector="
                f"{company_row['sector']!r} (real estate) for {ticker} "
                f"({company_row['full_name']}) -- a genuine sector-level "
                f"data field, not a name-based guess. No Sentinel-"
                f"disclosed text confirms a specific Dong Nai/Long Thanh "
                f"facility, so this is sector-plausible exposure, not "
                f"confirmed direct exposure."
            )
        else:
            classification = "HYPOTHETICAL"
            basis = (
                f"Sentinel's own `companies` table discloses sector="
                f"{company_row['sector']!r} for {ticker} "
                f"({company_row['full_name']}) -- not a real-estate/"
                f"industrial-park sector classification. Public "
                f"knowledge outside Sentinel's data suggests this "
                f"company has industrial land holdings, but Sentinel's "
                f"own governed data neither confirms nor addresses this, "
                f"so any link is a hypothesis, not a sector-supported "
                f"inference."
            )

        entity_mappings.append({
            "ticker": ticker,
            "classification": classification,
            "basis": basis,
        })
        findings.append(f"DERIVED_METRIC: entity mapping for {ticker} classified {classification} -- {basis}")
        evidence_refs.append(f"companies:symbol={ticker}" if company_row else f"companies:symbol={ticker}:NOT_FOUND")

        price_row = conn.execute(
            "SELECT date, close FROM prices_daily WHERE symbol=? "
            "AND date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' "
            "ORDER BY date DESC LIMIT 1",
            (ticker,),
        ).fetchone()
        decision_row = conn.execute(
            "SELECT decision_action, decision_score, created_at, execution_mode, execution_allowed "
            "FROM frontier_decisions WHERE symbol=? ORDER BY created_at DESC LIMIT 1",
            (ticker,),
        ).fetchone()

        if price_row:
            observations.append(
                f"OBSERVED_MARKET_FACT: {ticker} latest verified close price "
                f"is {price_row['close']} on {price_row['date']}"
            )
            evidence_refs.append(f"prices_daily:symbol={ticker}:date={price_row['date']}")

        if decision_row:
            findings.append(
                f"MODEL_ESTIMATE: {ticker} most recent Sentinel decision is "
                f"{decision_row['decision_action']!r} (score="
                f"{decision_row['decision_score']}, execution_mode="
                f"{decision_row['execution_mode']!r}, execution_allowed="
                f"{decision_row['execution_allowed']}) at "
                f"{decision_row['created_at']} -- this is Sentinel's own "
                f"decision-engine OUTPUT, NOT a validated predictor (see "
                f"SENTINEL_DECISION_ENGINE_AUDIT.md / "
                f"SENTINEL_REGIME_ENGINE_AUDIT.md: neither engine has any "
                f"historical validation). No profitability inference may "
                f"be drawn from it."
            )
            evidence_refs.append(f"frontier_decisions:symbol={ticker}")

    # macro context -- honestly stale, per SENTINEL_FRESHNESS_RESTORATION_EVIDENCE.md
    macro_row = conn.execute(
        "SELECT indicator, period, value FROM macro_indicators ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if macro_row:
        limitations.append(
            f"STALE_DATA: latest macro_indicators row (indicator="
            f"{macro_row['indicator']!r}, period={macro_row['period']}) is "
            f"far coarser/older than daily market data -- background "
            f"context only, not a current reading."
        )

    limitations.append(
        "None of the candidate tickers reach DIRECT classification -- "
        "Sentinel's own governed data does not disclose facility-level "
        "geographic exposure for any company. This is a genuine data "
        "limitation, not evidence of absent exposure."
    )
    limitations.append(
        "decision_engine/regime_detection outputs used above are FRESH "
        "(F5.1-restored) but NOT historically validated predictors -- "
        "see SENTINEL_DECISION_ENGINE_AUDIT.md and "
        "SENTINEL_REGIME_ENGINE_AUDIT.md."
    )
    risks.append(
        "RISK: no forecast is available (Sentinel has no forecasting "
        "capability, NOT_COMMISSIONED) -- any expectation of future price "
        "movement from this report would be unsupported speculation."
    )

    conn.close()

    report = build_report(
        institution="sentinel",
        mission_id=mission_id,
        objective="Assess plausible sector/company financial exposure to a DAT.AI zoning finding, read-only",
        operating_state=OperatingState.INTEGRATED,
        capability_statuses=[
            CapabilityStatus(
                name="cross_domain_entity_mapping",
                lifecycle=CapabilityLifecycle.TESTED,
                confidence=Confidence(value=0.4, basis=f"{len(entity_mappings)} candidate tickers checked against Sentinel's own companies table; 0 reached DIRECT"),
                evidence_refs=[f"companies:symbol={m['ticker']}" for m in entity_mappings],
                detail=json.dumps(entity_mappings),
            ),
        ],
        findings=findings,
        evidence_refs=evidence_refs,
        limitations=limitations,
        provenance_refs=[delegation_id, claim_id],
    )
    report.observations = observations
    report.risks = risks
    report.recommended_next_actions = [
        "RECOMMENDATION: request DAT.AI re-analysis with facility-level "
        "geographic disclosure (e.g. confirmed subsidiary land parcels) "
        "before any entity mapping can reach DIRECT",
        "RECOMMENDATION: continue monitoring KBC/SZC (INDIRECT, real-"
        "estate sector) for any disclosed Dong Nai/Long Thanh project "
        "announcement",
    ]

    report_id = str(uuid4())
    store.log_institutional_report(
        institution_id="sentinel",
        mission_id=mission_id,
        report_id=report_id,
        payload=report.model_dump(),
    )
    store.commit()

    # Execution-safety evidence, captured from THIS process, for the
    # F6 failure/negative-control tests to compare against.
    conn2 = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    exec_pairs_decisions = [tuple(r) for r in conn2.execute(
        "SELECT DISTINCT execution_mode, execution_allowed FROM frontier_decisions"
    )]
    exec_pairs_shadow = [tuple(r) for r in conn2.execute(
        "SELECT DISTINCT execution_mode, execution_allowed FROM frontier_shadow_executions"
    )]
    shadow_exec_count = conn2.execute("SELECT COUNT(*) FROM frontier_shadow_executions").fetchone()[0]
    conn2.close()

    result = {
        "pid": os.getpid(),
        "already_claimed": False,
        "mission_id": mission_id,
        "delegation_id": delegation_id,
        "claim_id": claim_id,
        "report_id": report_id,
        "entity_mappings": entity_mappings,
        "exec_pairs_decisions": exec_pairs_decisions,
        "exec_pairs_shadow": exec_pairs_shadow,
        "shadow_execution_count": shadow_exec_count,
        "federation_store_path": store_path,
        "resource_usage": meter.stop(),
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
