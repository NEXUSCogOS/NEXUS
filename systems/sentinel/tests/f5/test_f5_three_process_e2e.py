"""F5: Sentinel three-process federation integration tests.

Mirrors F4C's own three-process discipline (see
systems/librarian/tests/f4c/), substituting Sentinel as the third
specialist institution and its REAL, observed
financial_intelligence.db as the data source (read-only throughout).

Covers mission sections H (three-process E2E), J (financial epistemology),
K (live execution authority rejection), L (degraded-data negative
control), M (idempotency), N (process recovery).
"""

import json
import os
import subprocess
import sqlite3
import sys
from pathlib import Path

import pytest

FEDERATION_ROOT = str(Path(__file__).resolve().parents[3] / "nexus_federation")
SENTINEL_NEXUS_ROOT = str(Path(__file__).resolve().parents[2])
DAT_AI_ROOT = str(Path(FEDERATION_ROOT).parent / "dat_ai")
HELPERS_DIR = Path(__file__).resolve().parent / "_subprocess_helpers"
REAL_SENTINEL_DB = str(Path(SENTINEL_NEXUS_ROOT) / "financial_intelligence.db")

for _p in (FEDERATION_ROOT, SENTINEL_NEXUS_ROOT, DAT_AI_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ingress.contract_registry import bootstrap_federation_registry
from persistence.db import FederationStore
from kernel import FederationKernel
from contracts.generic import (
    CapabilityLifecycle,
    CapabilityStatus,
    Confidence,
    OperatingState,
    build_report,
)


@pytest.fixture
def federation_setup(tmp_path):
    db_path = tmp_path / "f5_federation.db"
    store = FederationStore(str(db_path))
    bootstrap_federation_registry()
    yield store, db_path


def _run(script_name, env):
    result = subprocess.run(
        [sys.executable, str(HELPERS_DIR / script_name)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"{script_name} failed (exit {result.returncode}):\n"
        f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )
    return json.loads(result.stdout)


def _env_base(store_path):
    env = os.environ.copy()
    env["FEDERATION_STORE_PATH"] = str(store_path)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


# ============================================================ SECTION H ===
def test_f5_full_three_process_e2e(federation_setup):
    """Process A (NEXUS) -> Process B (Sentinel) -> Process C (NEXUS)."""
    store, db_path = federation_setup
    env_base = _env_base(db_path)

    result_a = _run("process_a_nexus_delegation_creator.py", env_base)
    mission_id = result_a["mission_id"]
    delegation_id = result_a["delegation_id"]

    env_b = env_base.copy()
    env_b["MISSION_ID"] = mission_id
    env_b["DELEGATION_ID"] = delegation_id
    env_b["SENTINEL_DB_PATH"] = REAL_SENTINEL_DB
    result_b = _run("process_b_sentinel_analyst.py", env_b)

    assert result_b["analysis_executed"] is True
    assert result_b["already_claimed"] is False
    report_id = result_b["report_id"]

    env_c = env_base.copy()
    env_c["MISSION_ID"] = mission_id
    env_c["REPORT_ID"] = report_id
    result_c = _run("process_c_nexus_ingester.py", env_c)

    # ---- PID isolation ----
    pid_a, pid_b, pid_c = result_a["pid"], result_b["pid"], result_c["pid"]
    assert len({pid_a, pid_b, pid_c}) == 3, "all three processes must have distinct PIDs"

    # ---- ingestion accepted ----
    assert result_c["ingress_accepted"] is True, result_c["ingress_reason"]
    assert result_c["registry_entry_created"] is True

    # ---- report persists and is discoverable ----
    ingested = store.get_institutional_report(report_id)
    assert ingested is not None
    assert ingested["institution"] == "sentinel"
    assert ingested["operating_state"] == "DEGRADED"

    # ---- registry now has Sentinel ----
    registry = store.get_registry_entry("sentinel")
    assert registry is not None
    assert registry["institution_type"] == "financial_intelligence"

    # ---- Section O: provenance chain -- real identifiers, not placeholders
    import uuid as _uuid
    provenance_ids = result_c["provenance_ids"]
    assert provenance_ids, "kernel must produce at least one provenance/executive-state-event id"
    for pid in provenance_ids:
        _uuid.UUID(pid)  # raises ValueError if not a real UUID
    for real_id in (result_a["delegation_id"], result_b["claim_id"], result_b["report_id"], result_b["analysis_run_id"]):
        _uuid.UUID(real_id)

    print("\n=== F5 THREE-PROCESS E2E ===")
    print(f"PID_A={pid_a} PID_B={pid_b} PID_C={pid_c}")
    print(f"data_status={result_b['data_status']} age_days={result_b['age_days']}")
    print(f"regime_age_days={result_b['regime_age_days']}")
    print(f"ingress_accepted={result_c['ingress_accepted']}")
    print("\n--- provenance chain (Section O) ---")
    print(f"analysis_run_id={result_b['analysis_run_id']}")
    print(f"delegation_id={result_a['delegation_id']}")
    print(f"claim_id={result_b['claim_id']}")
    print(f"institutional_report_id={result_b['report_id']}")
    print(f"ingress_event_id=(institution_id=sentinel, cycle_id={result_b['report_id']})")
    print(f"executive_state_event_ids={provenance_ids}")


# ============================================================ SECTION J ===
def test_f5_financial_epistemology(federation_setup):
    """Every observation/finding is epistemically tagged; a forecast is
    never emitted as an observed fact; stale data is explicitly marked."""
    store, db_path = federation_setup
    env_base = _env_base(db_path)

    result_a = _run("process_a_nexus_delegation_creator.py", env_base)
    env_b = env_base.copy()
    env_b["MISSION_ID"] = result_a["mission_id"]
    env_b["DELEGATION_ID"] = result_a["delegation_id"]
    env_b["SENTINEL_DB_PATH"] = REAL_SENTINEL_DB
    result_b = _run("process_b_sentinel_analyst.py", env_b)

    report = store.get_institutional_report(result_b["report_id"])

    # No FORECAST-tagged statement anywhere -- Sentinel has no forecasting
    # capability and must never fabricate one.
    all_text = " ".join(report["observations"] + report["findings"])
    assert "FORECAST:" not in all_text, "Sentinel must never emit a FORECAST-tagged statement"

    # observations must be OBSERVED_MARKET_FACT only
    for obs in report["observations"]:
        assert obs.startswith("OBSERVED_MARKET_FACT:"), f"non-fact string in observations: {obs}"

    # findings must be DERIVED_METRIC or MODEL_ESTIMATE (never a bare
    # unqualified claim, never a recommendation)
    for f in report["findings"]:
        assert f.startswith(("DERIVED_METRIC:", "MODEL_ESTIMATE:")), f"untagged finding: {f}"

    # recommendations only ever appear in recommended_next_actions
    for r in report["recommended_next_actions"]:
        assert r.startswith("RECOMMENDATION:"), f"untagged recommendation: {r}"
    assert not any("RECOMMENDATION:" in o for o in report["observations"])
    assert not any("RECOMMENDATION:" in f for f in report["findings"])

    # stale data is explicitly marked, not silently presented as current
    limitations_text = " ".join(report["limitations"])
    if not result_b["current_regime_conclusion_permitted"]:
        assert (
            "DERIVED_METRIC:" in " ".join(report["findings"])
            and "days old and is NOT presented as the current market regime" in " ".join(report["findings"])
        ), "stale regime must be explicitly disclaimed, not silently presented as current"

    print("\n=== F5 FINANCIAL EPISTEMOLOGY ===")
    print(f"observations={len(report['observations'])} all OBSERVED_MARKET_FACT: PASS")
    print(f"findings={len(report['findings'])} all DERIVED_METRIC/MODEL_ESTIMATE: PASS")
    print("no FORECAST-tagged statement: PASS")


# ============================================================ SECTION L ===
def test_f5_degraded_data_negative_control(federation_setup):
    """A current conclusion is refused when the underlying data exceeds
    the freshness threshold -- never fabricated.

    F5.1 (2026-08-28) restored the signal/decision/regime pipeline, so
    regime -- this test's original target -- is now genuinely current and
    can no longer serve as the stale example. macro_indicators, however,
    remains durably coarse (latest period recorded: 2023-01-01, a
    quarterly/annual-cadence series, not something a daily pipeline fix
    changes) -- it is the honest choice of a component that stays stale
    regardless of how current the rest of the pipeline is."""
    store, db_path = federation_setup
    env_base = _env_base(db_path)

    result_a = _run("process_a_nexus_delegation_creator.py", env_base)
    env_b = env_base.copy()
    env_b["MISSION_ID"] = result_a["mission_id"]
    env_b["DELEGATION_ID"] = result_a["delegation_id"]
    env_b["SENTINEL_DB_PATH"] = REAL_SENTINEL_DB
    result_b = _run("process_b_sentinel_analyst.py", env_b)

    report = store.get_institutional_report(result_b["report_id"])
    macro_component = next(
        c for c in report["capability_statuses"] if c["name"] == "macro_data"
    )
    # macro_data is INTEGRATED (real rows exist) but the report must
    # explicitly disclaim it as background/stale, never present it as a
    # current reading.
    limitations_text = " ".join(report["limitations"])
    assert "STALE_DATA" in limitations_text and "macro_indicators" in limitations_text, (
        "macro_indicators staleness must be explicitly disclaimed in limitations"
    )
    assert "period=2023" in limitations_text, (
        "the actual stale period must be stated, not silently omitted"
    )

    # And regime -- now genuinely current -- must NOT be treated as
    # equally reliable to a fabricated same-day quote: it's a real,
    # current MODEL_ESTIMATE, not an OBSERVED_MARKET_FACT.
    regime_component = next(
        c for c in report["capability_statuses"] if c["name"] == "regime_detection"
    )
    assert regime_component["lifecycle"] == "INTEGRATED"
    assert any(
        f.startswith("MODEL_ESTIMATE:") and "composite_regime_score" in f
        for f in report["findings"]
    ), "regime output must be tagged MODEL_ESTIMATE, never OBSERVED_MARKET_FACT"

    # No fabricated "current" quote or invented market state -- the report
    # must say WHICH date the regime describes, not merely assert a label.
    assert "market_date=" in " ".join(report["observations"])

    print("\n=== F5 DEGRADED-DATA NEGATIVE CONTROL ===")
    print(f"macro_data lifecycle={macro_component['lifecycle']} (durably stale, period=2023)")
    print(f"regime_detection lifecycle={regime_component['lifecycle']} (now current, tagged MODEL_ESTIMATE)")
    print("Stale component explicitly disclaimed, current component correctly tagged: PASS")


# ============================================================ SECTION K ===
def test_f5_live_execution_rejected(federation_setup):
    """A delegation requesting a live order is rejected before any code
    that could place one ever runs. Real before/after DB evidence against
    the ACTUAL production financial_intelligence.db."""
    store, db_path = federation_setup
    env_base = _env_base(db_path)

    # ---- BEFORE: real DB state ----
    conn = sqlite3.connect(f"file:{REAL_SENTINEL_DB}?mode=ro", uri=True)
    before_decisions = list(conn.execute(
        "SELECT DISTINCT execution_mode, execution_allowed FROM frontier_decisions"
    ))
    before_shadow = list(conn.execute(
        "SELECT DISTINCT execution_mode, execution_allowed FROM frontier_shadow_executions"
    ))
    before_decision_count = conn.execute("SELECT COUNT(*) FROM frontier_decisions").fetchone()[0]
    before_shadow_count = conn.execute("SELECT COUNT(*) FROM frontier_shadow_executions").fetchone()[0]
    conn.close()

    result = _run("process_a_live_order_rejection.py", env_base)

    # ---- AFTER: real DB state ----
    conn = sqlite3.connect(f"file:{REAL_SENTINEL_DB}?mode=ro", uri=True)
    after_decisions = list(conn.execute(
        "SELECT DISTINCT execution_mode, execution_allowed FROM frontier_decisions"
    ))
    after_shadow = list(conn.execute(
        "SELECT DISTINCT execution_mode, execution_allowed FROM frontier_shadow_executions"
    ))
    after_decision_count = conn.execute("SELECT COUNT(*) FROM frontier_decisions").fetchone()[0]
    after_shadow_count = conn.execute("SELECT COUNT(*) FROM frontier_shadow_executions").fetchone()[0]
    conn.close()

    assert result["authority_rejected"] is True, result["rejection_reason"]
    assert "exceeds the phase ceiling" in result["rejection_reason"]
    assert result["delegation_count_unchanged"] is True

    assert before_decisions == after_decisions, "execution_mode/execution_allowed values changed"
    assert before_shadow == after_shadow, "shadow execution_mode/execution_allowed values changed"
    assert before_decision_count == after_decision_count, "frontier_decisions row count changed"
    assert before_shadow_count == after_shadow_count, "frontier_shadow_executions row count changed"

    print("\n=== F5 LIVE EXECUTION AUTHORITY REJECTION ===")
    print(f"authority_rejected={result['authority_rejected']}")
    print(f"reason: {result['rejection_reason'][:120]}...")
    print(f"frontier_decisions distinct (execution_mode, execution_allowed) before=after={before_decisions}")
    print(f"frontier_shadow_executions distinct before=after={before_shadow}")
    print("No order API call, no broker invocation, no execution state change: PASS")


# ============================================================ SECTION M ===
def test_f5_idempotency_claim_guard(federation_setup):
    """Same delegation claimed twice -> Process B runs its analysis
    exactly once. The second invocation observes already_claimed=True and
    performs no analysis, no second report."""
    store, db_path = federation_setup
    env_base = _env_base(db_path)

    result_a = _run("process_a_nexus_delegation_creator.py", env_base)
    env_b = env_base.copy()
    env_b["MISSION_ID"] = result_a["mission_id"]
    env_b["DELEGATION_ID"] = result_a["delegation_id"]
    env_b["SENTINEL_DB_PATH"] = REAL_SENTINEL_DB

    result_b1 = _run("process_b_sentinel_analyst.py", env_b)
    assert result_b1["analysis_executed"] is True
    assert result_b1["already_claimed"] is False

    # Replay: same delegation, fresh subprocess, same environment.
    result_b2 = _run("process_b_sentinel_analyst.py", env_b)
    assert result_b2["already_claimed"] is True
    assert result_b2["analysis_executed"] is False
    assert result_b2["report_id"] is None

    reports_count = store.count_reports("sentinel")
    assert reports_count == 1, "exactly one report must exist after a replayed claim"

    print("\n=== F5 IDEMPOTENCY (CLAIM GUARD) ===")
    print(f"first claim: already_claimed={result_b1['already_claimed']} analysis_executed={result_b1['analysis_executed']}")
    print(f"replay claim: already_claimed={result_b2['already_claimed']} analysis_executed={result_b2['analysis_executed']}")
    print(f"reports in store: {reports_count}")


# ============================================================ SECTION N ===
def test_f5_process_c_recovery(federation_setup):
    """Process C fails/absent after Process B persists its report; a later
    fresh Process C consumes the report exactly once, safely."""
    store, db_path = federation_setup
    env_base = _env_base(db_path)

    result_a = _run("process_a_nexus_delegation_creator.py", env_base)
    env_b = env_base.copy()
    env_b["MISSION_ID"] = result_a["mission_id"]
    env_b["DELEGATION_ID"] = result_a["delegation_id"]
    env_b["SENTINEL_DB_PATH"] = REAL_SENTINEL_DB
    result_b = _run("process_b_sentinel_analyst.py", env_b)
    report_id = result_b["report_id"]

    # Simulate Process C being absent/failed: report is persisted but not
    # yet ingested. Verify it survives that gap.
    persisted = store.get_institutional_report(report_id)
    assert persisted is not None

    env_c = env_base.copy()
    env_c["MISSION_ID"] = result_a["mission_id"]
    env_c["REPORT_ID"] = report_id

    result_c1 = _run("process_c_nexus_ingester.py", env_c)
    assert result_c1["ingress_accepted"] is True

    registry_after_first = store.get_registry_entry("sentinel")
    assert registry_after_first is not None

    # Later fresh Process C retry (crash-recovery simulation).
    result_c2 = _run("process_c_nexus_ingester.py", env_c)
    assert result_c2["ingress_accepted"] is True

    registry_after_second = store.get_registry_entry("sentinel")
    assert registry_after_second is not None

    report_after_retry = store.get_institutional_report(report_id)
    assert report_after_retry == persisted, "report must not be modified by retry ingestion"

    print("\n=== F5 PROCESS RECOVERY ===")
    print(f"first ingestion accepted={result_c1['ingress_accepted']}")
    print(f"retry ingestion accepted={result_c2['ingress_accepted']}")
    print("report unchanged after retry: PASS")


# ============================================================ SECTION 20 ==
def test_f5_report_replay_receipt_vs_state_transition(federation_setup):
    """F5.1 section 20: replay the SAME InstitutionalReport and prove the
    kernel's existing, pre-built distinction: a RECEIPT event is logged
    every time (report_log grows), but a STATE TRANSITION happens at most
    once (registry + state_event_log do not grow on replay).

    This is not new kernel behavior -- kernel.py's own DUPLICATE branch
    (temporal classification) already implements exactly this split
    ("Log the duplicate attempt ... but do NOT re-run evidence resolution
    or touch the registry/state-event tables"). This test is the first to
    assert it explicitly for Sentinel specifically, with real row counts."""
    store, db_path = federation_setup
    env_base = _env_base(db_path)

    result_a = _run("process_a_nexus_delegation_creator.py", env_base)
    env_b = env_base.copy()
    env_b["MISSION_ID"] = result_a["mission_id"]
    env_b["DELEGATION_ID"] = result_a["delegation_id"]
    env_b["SENTINEL_DB_PATH"] = REAL_SENTINEL_DB
    result_b = _run("process_b_sentinel_analyst.py", env_b)
    report_id = result_b["report_id"]

    env_c = env_base.copy()
    env_c["MISSION_ID"] = result_a["mission_id"]
    env_c["REPORT_ID"] = report_id

    result_c1 = _run("process_c_nexus_ingester.py", env_c)
    assert result_c1["ingress_accepted"] is True
    reports_after_first = store.count_reports("sentinel")
    state_events_after_first = store.count_state_events("sentinel")
    provenance_ids_first = set(result_c1["provenance_ids"])
    assert state_events_after_first > 0, "first ingestion must create executive-state events"

    # Replay: the exact same report_id, a fresh Process C subprocess.
    result_c2 = _run("process_c_nexus_ingester.py", env_c)
    assert result_c2["ingress_accepted"] is True
    reports_after_replay = store.count_reports("sentinel")
    state_events_after_replay = store.count_state_events("sentinel")

    # RECEIPT EVENT duplication: report_log grows -- every ingestion
    # ATTEMPT is durably recorded, replay included. This is intentional
    # audit-trail behavior, not a bug to suppress.
    assert reports_after_replay > reports_after_first, (
        "a replayed ingestion attempt must still be recorded as a receipt "
        "event -- report_log rows are an append-only attempt log, not a "
        "dedup table"
    )

    # STATE TRANSITION duplication: state_event_log must NOT grow -- the
    # replay is classified DUPLICATE and the kernel's own code path
    # explicitly skips evidence re-resolution and registry/state-event
    # writes for that classification.
    assert state_events_after_replay == state_events_after_first, (
        "a replayed report must not create new executive-state-event rows "
        "-- exactly one semantic state transition per real report"
    )

    # The kernel result on replay must say DUPLICATE, not silently look
    # identical to a first-time accept.
    assert result_c2["temporal_classification"] == "DUPLICATE", (
        f"replay must be classified DUPLICATE, got "
        f"{result_c2['temporal_classification']!r}"
    )

    print("\n=== F5 REPORT REPLAY IDEMPOTENCY (Section 20) ===")
    print(f"report_log rows: {reports_after_first} -> {reports_after_replay} (receipt duplication: EXPECTED, growing)")
    print(f"state_event_log rows: {state_events_after_first} -> {state_events_after_replay} (state duplication: NONE, must be equal)")
    print(f"replay temporal_classification={result_c2['temporal_classification']}")
    print("Receipt event duplication vs state transition duplication correctly distinguished: PASS")


# ============================================================ SECTION 18 ==
def test_f5_1_nexus_state_transition_stale_to_current(federation_setup):
    """F5.1 section 18: prove NEXUS's executive state actually transitions
    from a decision/regime-stale report to the new evidence-supported
    (current) state, with the transition preserved in state_event_log
    (prior_lifecycle -> new_lifecycle), not merely overwritten silently.

    Ingests a synthetic "before F5.1" Sentinel report (regime_detection/
    decision_engine DEGRADED -- exactly what the real report looked like
    prior to this mission's pipeline restoration, per
    SENTINEL_INSTITUTIONAL_REPORT.md's F5 Phase 4 findings) directly
    through the SAME generic kernel path real reports use, then ingests
    the REAL current report from Process B into the same store, and
    reads back the actual transition NEXUS recorded.
    """
    store, db_path = federation_setup
    kernel = FederationKernel(store)

    from datetime import datetime, timezone
    from uuid import uuid4

    # ---- "Before" report: synthetic, but shaped exactly like the real
    # pre-restoration state (mirrors SENTINEL_INSTITUTIONAL_REPORT.md).
    stale_mission_id = str(uuid4())
    stale_report = build_report(
        institution="sentinel",
        mission_id=stale_mission_id,
        objective="F5.1 test fixture: pre-restoration Sentinel state",
        operating_state=OperatingState.DEGRADED,
        capability_statuses=[
            CapabilityStatus(
                name="regime_detection",
                lifecycle=CapabilityLifecycle.DEGRADED,
                confidence=Confidence(value=0.5, basis="pre-restoration fixture"),
                evidence_refs=["fixture:pre_f5_1_regime_stale"],
                detail="regime last generated 2026-08-14, 13 days stale",
            ),
            CapabilityStatus(
                name="decision_engine",
                lifecycle=CapabilityLifecycle.DEGRADED,
                confidence=Confidence(value=0.5, basis="pre-restoration fixture"),
                evidence_refs=["fixture:pre_f5_1_decisions_stale"],
                detail="frontier_decisions last written 2026-08-14",
            ),
        ],
        findings=["DERIVED_METRIC: fixture representing pre-F5.1 state"],
        evidence_refs=["fixture:pre_f5_1_regime_stale", "fixture:pre_f5_1_decisions_stale"],
    )

    result_before = kernel.ingest_report(
        raw_payload=stale_report.model_dump(),
        now=datetime.now(timezone.utc),
    )
    assert result_before.accepted is True

    registry_before = store.get_registry_entry("sentinel")
    regime_state_before = next(
        c for c in registry_before["component_states"]
        if c["capability_name"] == "regime_detection"
    )
    assert regime_state_before["reported_lifecycle"] == "DEGRADED"

    # ---- "After" report: the REAL current report, via the real
    # three-process path (Process A creates delegation, Process B runs
    # the real analysis executor against the real database).
    result_a = _run("process_a_nexus_delegation_creator.py", _env_base(db_path))
    env_b = _env_base(db_path)
    env_b["MISSION_ID"] = result_a["mission_id"]
    env_b["DELEGATION_ID"] = result_a["delegation_id"]
    env_b["SENTINEL_DB_PATH"] = REAL_SENTINEL_DB
    result_b = _run("process_b_sentinel_analyst.py", env_b)

    env_c = _env_base(db_path)
    env_c["MISSION_ID"] = result_a["mission_id"]
    env_c["REPORT_ID"] = result_b["report_id"]
    result_c = _run("process_c_nexus_ingester.py", env_c)
    assert result_c["ingress_accepted"] is True

    registry_after = store.get_registry_entry("sentinel")
    regime_state_after = next(
        c for c in registry_after["component_states"]
        if c["capability_name"] == "regime_detection"
    )

    # The actual F5.1 restoration makes regime current again (see
    # SENTINEL_FRESHNESS_RESTORATION_EVIDENCE.md) -- assert against the
    # real, current classification, not a hardcoded assumption.
    assert regime_state_after["reported_lifecycle"] == "INTEGRATED", (
        "expected the restored pipeline to report regime_detection as "
        "INTEGRATED; if this fails, the pipeline may have regressed to "
        "stale -- re-run SENTINEL_FRESHNESS_RESTORATION_EVIDENCE.md's "
        "live cycle before assuming this test is wrong"
    )

    # ---- The transition itself, preserved in state_event_log.
    events = store.get_state_events("sentinel", capability_name="regime_detection")
    assert len(events) >= 2, "expected at least two recorded events: initial DEGRADED, then transition to INTEGRATED"

    lifecycles_in_order = [e["new_lifecycle"] for e in events]
    assert lifecycles_in_order[0] == "DEGRADED"
    assert lifecycles_in_order[-1] == "INTEGRATED"

    # Find the actual transition record and confirm prior_lifecycle is set.
    transition = next(
        e for e in events
        if e["prior_lifecycle"] == "DEGRADED" and e["new_lifecycle"] == "INTEGRATED"
    )
    assert transition is not None

    print("\n=== F5.1 NEXUS STATE TRANSITION (Section 18) ===")
    print(f"regime_detection BEFORE: {regime_state_before['reported_lifecycle']}")
    print(f"regime_detection AFTER:  {regime_state_after['reported_lifecycle']}")
    print(f"recorded transition: {transition['prior_lifecycle']} -> {transition['new_lifecycle']}")
    print(f"total state_event_log rows for regime_detection: {len(events)}")
    print("Historical transition preserved, not silently overwritten: PASS")
