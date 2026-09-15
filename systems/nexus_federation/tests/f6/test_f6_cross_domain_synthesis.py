"""F6: Cross-domain cognitive orchestration -- real DAT.AI trigger,
independent Librarian + Sentinel delegation, executive synthesis.

Four-process pipeline (mission section 8):
  Process A (dat_ai trigger source) -- separate helper, run once per test
             to seed a real, freshly-ingested DAT.AI report
  Process A (nexus trigger+route)   -- relevance assessment, delegations
  Process B (librarian)             -- independent research
  Process C (sentinel)              -- independent financial analysis
  Process D (nexus synthesis)       -- ingest both, synthesize, persist
"""

import json
import os
import subprocess
import sqlite3
import sys
from pathlib import Path

import pytest

FEDERATION_ROOT = str(Path(__file__).resolve().parents[2])
DAT_AI_ROOT = str(Path(FEDERATION_ROOT).parent / "dat_ai")
SENTINEL_NEXUS_ROOT = str(Path(FEDERATION_ROOT).parent / "sentinel")
HELPERS_DIR = Path(__file__).resolve().parent / "_subprocess_helpers"
REAL_SENTINEL_DB = str(Path(SENTINEL_NEXUS_ROOT) / "financial_intelligence.db")

for _p in (FEDERATION_ROOT, DAT_AI_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ingress.contract_registry import bootstrap_federation_registry
from persistence.db import FederationStore


@pytest.fixture
def federation_setup(tmp_path):
    db_path = tmp_path / "f6_federation.db"
    store = FederationStore(str(db_path))
    bootstrap_federation_registry()
    yield store, db_path


def _run(script_name, env, timeout=60):
    result = subprocess.run(
        [sys.executable, str(HELPERS_DIR / script_name)],
        env=env, capture_output=True, text=True, timeout=timeout,
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


def _seed_real_dat_ai_trigger(env_base):
    return _run("process_dat_ai_trigger_source.py", env_base)


# ============================================================ SECTION 8/31 =
def test_f6_full_four_process_e2e(federation_setup):
    store, db_path = federation_setup
    env_base = _env_base(db_path)

    dat_ai_result = _seed_real_dat_ai_trigger(env_base)
    assert dat_ai_result["ingress_accepted"] is True

    result_a = _run("process_a_nexus_trigger_and_route.py", env_base)
    assert result_a["librarian_relevance"]["relevant"] is True
    assert result_a["sentinel_relevance"]["relevant"] is True
    assert len(result_a["delegations_created"]) == 2

    lib_deleg = next(d for d in result_a["delegations_created"] if d["recipient"] == "librarian")
    sen_deleg = next(d for d in result_a["delegations_created"] if d["recipient"] == "sentinel")

    env_b = env_base.copy()
    env_b["MISSION_ID"] = lib_deleg["mission_id"]
    env_b["DELEGATION_ID"] = lib_deleg["delegation_id"]
    result_b = _run("process_b_librarian_research.py", env_b)
    assert result_b["already_claimed"] is False

    env_c = env_base.copy()
    env_c["MISSION_ID"] = sen_deleg["mission_id"]
    env_c["DELEGATION_ID"] = sen_deleg["delegation_id"]
    env_c["SENTINEL_DB_PATH"] = REAL_SENTINEL_DB
    result_c = _run("process_c_sentinel_analysis.py", env_c)
    assert result_c["already_claimed"] is False

    # Execution safety, captured inside Process C itself.
    assert result_c["exec_pairs_decisions"] == [["SHADOW", 0]]
    assert result_c["exec_pairs_shadow"] == [["SHADOW", 0]]

    env_d = env_base.copy()
    env_d["TRIGGER_ID"] = result_a["trigger_id"]
    env_d["LIBRARIAN_REPORT_ID"] = result_b["report_id"]
    env_d["SENTINEL_REPORT_ID"] = result_c["report_id"]
    env_d["TRIGGER_EVIDENCE_REFS_JSON"] = json.dumps(dat_ai_result.get("provenance_ids", []))
    env_d["TRIGGER_PROVENANCE_REFS_JSON"] = json.dumps(dat_ai_result.get("provenance_ids", []))
    result_d = _run("process_d_nexus_synthesis.py", env_d)

    assert result_d["librarian_ingress_accepted"] is True
    assert result_d["sentinel_ingress_accepted"] is True
    assert result_d["partial"] is False

    pids = {result_a["pid"], result_b["pid"], result_c["pid"], result_d["pid"]}
    assert len(pids) == 4, "all four processes must have distinct PIDs"

    print("\n=== F6 FOUR-PROCESS E2E ===")
    print(f"PID_A={result_a['pid']} PID_B={result_b['pid']} PID_C={result_c['pid']} PID_D={result_d['pid']}")
    print(f"trigger_id={result_a['trigger_id']}")
    print(f"executive_conclusion_class={result_d['executive_conclusion_class']}")
    print(f"executive_conclusion={result_d['executive_conclusion']}")


# ============================================================ SECTION 21 ==
def test_f6_specialist_failure_partial_synthesis(federation_setup):
    """One recipient (Sentinel) unavailable -- NEXUS retains Librarian's
    result, marks Sentinel missing, produces a PARTIAL synthesis, never
    fabricates Sentinel's contribution."""
    store, db_path = federation_setup
    env_base = _env_base(db_path)

    dat_ai_result = _seed_real_dat_ai_trigger(env_base)
    result_a = _run("process_a_nexus_trigger_and_route.py", env_base)
    lib_deleg = next(d for d in result_a["delegations_created"] if d["recipient"] == "librarian")

    env_b = env_base.copy()
    env_b["MISSION_ID"] = lib_deleg["mission_id"]
    env_b["DELEGATION_ID"] = lib_deleg["delegation_id"]
    result_b = _run("process_b_librarian_research.py", env_b)

    # Sentinel is simulated unavailable: Process C is never run.
    env_d = env_base.copy()
    env_d["TRIGGER_ID"] = result_a["trigger_id"]
    env_d["LIBRARIAN_REPORT_ID"] = result_b["report_id"]
    # SENTINEL_REPORT_ID intentionally omitted
    env_d["TRIGGER_EVIDENCE_REFS_JSON"] = json.dumps(dat_ai_result.get("provenance_ids", []))
    env_d["TRIGGER_PROVENANCE_REFS_JSON"] = json.dumps(dat_ai_result.get("provenance_ids", []))
    result_d = _run("process_d_nexus_synthesis.py", env_d)

    assert result_d["partial"] is True
    assert "sentinel" in result_d["missing_institutions"]
    assert "librarian" not in result_d["missing_institutions"]
    assert result_d["librarian_ingress_accepted"] is True
    assert result_d["sentinel_ingress_accepted"] is None
    assert result_d["executive_conclusion_class"] == "INSUFFICIENT_EVIDENCE"

    print("\n=== F6 SPECIALIST FAILURE (Section 21) ===")
    print(f"missing_institutions={result_d['missing_institutions']}")
    print(f"librarian retained: {result_d['librarian_ingress_accepted']}")
    print(f"executive_conclusion_class={result_d['executive_conclusion_class']} (partial, not fabricated)")


# ============================================================ SECTION 22 ==
def test_f6_contradiction_preserved_with_fixtures(federation_setup):
    """Controlled test fixtures ONLY (mission section 22 explicit
    instruction) -- proves NEXUS preserves contradiction between two
    reports rather than suppressing one to force coherence. Not evidence
    of any real-world F6 conclusion."""
    store, db_path = federation_setup
    from synthesis.cross_domain_synthesis import synthesize, ExecutiveConclusionClass

    librarian_fixture = {
        "cycle_id": "fixture-librarian-report",
        "evidence_refs": ["fixture:policy_doc_A"],
        "provenance_refs": ["fixture:prov_lib"],
        "uncertainty": [],
        "limitations": [],
        "findings": ["CONSENSUS: policy context suggests potential material economic impact"],
        "cross_system_implications": [],
    }
    sentinel_fixture = {
        "cycle_id": "fixture-sentinel-report",
        "evidence_refs": ["fixture:market_data_B"],
        "provenance_refs": ["fixture:prov_sen"],
        "uncertainty": [],
        "limitations": [],
        "findings": ["CONTRADICTORY: available financial data shows no supported market/company implication"],
        "cross_system_implications": [],
    }

    synthesis = synthesize(
        trigger_id="fixture-trigger",
        trigger_evidence_refs=["fixture:trigger_evidence"],
        trigger_provenance_refs=["fixture:trigger_prov"],
        dat_ai_observation_ts="2025-10-13T03:40:37+00:00",
        librarian_report=librarian_fixture,
        sentinel_report=sentinel_fixture,
    )

    assert synthesis.executive_conclusion_class == ExecutiveConclusionClass.CONTRADICTORY_EVIDENCE
    assert any("LIBRARIAN" in f for f in synthesis.supporting_findings)
    assert any("SENTINEL" in f for f in synthesis.contradictory_findings)
    # Neither institution's finding text is missing/suppressed.
    all_text = " ".join(synthesis.supporting_findings + synthesis.contradictory_findings)
    assert "policy context suggests potential material economic impact" in all_text
    assert "no supported market/company implication" in all_text

    print("\n=== F6 CONTRADICTION HANDLING (Section 22, fixture-only) ===")
    print(f"executive_conclusion_class={synthesis.executive_conclusion_class.value}")
    print("Both institutions' positions preserved, neither suppressed: PASS")


# ============================================================ SECTION 23 ==
def test_f6_duplicate_trigger_replay_no_duplicate_missions(federation_setup):
    """Same DAT.AI trigger replayed -> Process A must not create a second
    pair of delegations for the identical (institution, cycle_id,
    capability, category) tuple."""
    store, db_path = federation_setup
    env_base = _env_base(db_path)

    dat_ai_result = _seed_real_dat_ai_trigger(env_base)

    result_a1 = _run("process_a_nexus_trigger_and_route.py", env_base)
    delegations_before = store.count_delegations()
    assert all(not d["already_existed"] for d in result_a1["delegations_created"])

    # Replay: Process A runs again against the SAME DAT.AI report (still
    # the "last accepted" one -- nothing new was ingested). trigger_id is
    # deterministic (UUID5 of source_report_id + source_finding_id), so
    # this reproduces the IDENTICAL trigger_id, and therefore the
    # identical mission_id/proposal_id for each recipient.
    result_a2 = _run("process_a_nexus_trigger_and_route.py", env_base)
    delegations_after = store.count_delegations()

    assert result_a1["trigger_id"] == result_a2["trigger_id"], "replay against the same DAT.AI report must reproduce the same trigger_id"
    assert all(d["already_existed"] for d in result_a2["delegations_created"]), "replay must recognize both delegations as already existing"
    assert delegations_after == delegations_before, "no new delegation rows may be created by a trigger replay"

    for d1, d2 in zip(
        sorted(result_a1["delegations_created"], key=lambda d: d["recipient"]),
        sorted(result_a2["delegations_created"], key=lambda d: d["recipient"]),
    ):
        assert d1["delegation_id"] == d2["delegation_id"]
        assert d1["mission_id"] == d2["mission_id"]

    print("\n=== F6 DUPLICATE TRIGGER REPLAY (Section 23) ===")
    print(f"trigger_id (identical both runs): {result_a1['trigger_id']}")
    print(f"delegations before second run: {delegations_before}, after: {delegations_after} (unchanged)")
    print("No duplicate specialist missions created on trigger replay: PASS")


# ============================================================ SECTION 28 ==
def test_f6_negative_control_no_material_effect(federation_setup):
    """A trigger whose cross-domain significance is deliberately
    unsupported -- the OTHER real, DAT.AI-ingested zone (C4, a routine
    subdivision plan for already-built-up Bien Hoa city, NOT adjacent to
    major new infrastructure) with no candidate_implications proposed.
    Expected: neither institution is routed to."""
    store, db_path = federation_setup
    env_base = _env_base(db_path)

    _seed_real_dat_ai_trigger(env_base)

    env_a = env_base.copy()
    env_a["F6_ZONE_PROJECT_ID"] = "c4"
    env_a["F6_ZONE_ADMIN_CODE"] = "26380"
    env_a["F6_TRIGGER_GEOGRAPHY_OVERRIDE"] = "Bien Hoa city, Dong Nai province, Vietnam"
    env_a["F6_TRIGGER_MATERIALITY"] = "0.2"
    env_a["F6_TRIGGER_IMPLICATIONS_OVERRIDE"] = json.dumps([])  # no candidate implications proposed

    result_a = _run("process_a_nexus_trigger_and_route.py", env_a)

    assert result_a["librarian_relevance"]["relevant"] is False
    assert result_a["sentinel_relevance"]["relevant"] is False
    assert len(result_a["delegations_created"]) == 0

    print("\n=== F6 NEGATIVE CONTROL (Section 28) ===")
    print(f"candidate_implications={result_a['candidate_implications']}")
    print(f"librarian_relevance={result_a['librarian_relevance']['relevant']}")
    print(f"sentinel_relevance={result_a['sentinel_relevance']['relevant']}")
    print("NO_MATERIAL_CROSS_DOMAIN_EFFECT_ESTABLISHED (no delegation created): PASS")


# ============================================================ SECTION 23 ==
def test_f6_process_d_restart_no_duplicate_synthesis(federation_setup):
    """Process D delayed/restarted -> synthesis occurs exactly once
    semantically. Receipt logs (report_log, observability_event_log) may
    grow on replay; the semantic state transition (state_event_log) must
    not."""
    store, db_path = federation_setup
    env_base = _env_base(db_path)

    dat_ai_result = _seed_real_dat_ai_trigger(env_base)
    result_a = _run("process_a_nexus_trigger_and_route.py", env_base)
    lib_deleg = next(d for d in result_a["delegations_created"] if d["recipient"] == "librarian")
    sen_deleg = next(d for d in result_a["delegations_created"] if d["recipient"] == "sentinel")

    env_b = env_base.copy()
    env_b["MISSION_ID"] = lib_deleg["mission_id"]
    env_b["DELEGATION_ID"] = lib_deleg["delegation_id"]
    result_b = _run("process_b_librarian_research.py", env_b)

    env_c = env_base.copy()
    env_c["MISSION_ID"] = sen_deleg["mission_id"]
    env_c["DELEGATION_ID"] = sen_deleg["delegation_id"]
    env_c["SENTINEL_DB_PATH"] = REAL_SENTINEL_DB
    result_c = _run("process_c_sentinel_analysis.py", env_c)

    env_d = env_base.copy()
    env_d["TRIGGER_ID"] = result_a["trigger_id"]
    env_d["LIBRARIAN_REPORT_ID"] = result_b["report_id"]
    env_d["SENTINEL_REPORT_ID"] = result_c["report_id"]
    env_d["TRIGGER_EVIDENCE_REFS_JSON"] = json.dumps(dat_ai_result.get("provenance_ids", []))
    env_d["TRIGGER_PROVENANCE_REFS_JSON"] = json.dumps(dat_ai_result.get("provenance_ids", []))

    result_d1 = _run("process_d_nexus_synthesis.py", env_d)
    state_events_after_first = store.count_state_events("nexus")
    reports_after_first = store.count_reports("librarian") + store.count_reports("sentinel")

    # "Delayed/restarted": a fresh Process D subprocess, same reports.
    result_d2 = _run("process_d_nexus_synthesis.py", env_d)
    state_events_after_second = store.count_state_events("nexus")
    reports_after_second = store.count_reports("librarian") + store.count_reports("sentinel")

    # Receipt-event duplication: report_log grows (each report is
    # re-ingested and re-logged as a receipt, same as F5.1 section 20's
    # kernel behavior) -- this is intentional, not a bug.
    assert reports_after_second > reports_after_first, (
        "a replayed ingestion attempt must still be recorded as a receipt event"
    )

    # State-transition duplication: state_event_log must NOT grow --
    # exactly one semantic synthesis per (librarian_report, sentinel_report)
    # pair, even though Process D itself ran twice.
    assert state_events_after_second == state_events_after_first, (
        "a restarted Process D must not create a second executive-state "
        "event for the same pair of reports"
    )
    assert result_d1["synthesis_id"] != result_d2["synthesis_id"], (
        "each Process D invocation computes its own synthesis object in "
        "memory (that part is not itself deduplicated) -- what matters is "
        "that only ONE of them is reflected in persisted executive state, "
        "asserted above via state_event_log's row count"
    )
    assert result_d1["executive_conclusion_class"] == result_d2["executive_conclusion_class"], (
        "re-deriving synthesis from the same two reports must reach the same conclusion class"
    )

    print("\n=== F6 PROCESS D RESTART (Section 23) ===")
    print(f"state_event_log rows (nexus): {state_events_after_first} -> {state_events_after_second} (unchanged)")
    print(f"report_log rows (receipt events): {reports_after_first} -> {reports_after_second} (grew, expected)")
    print(f"synthesis_id run1={result_d1['synthesis_id']} run2={result_d2['synthesis_id']} (different objects, same persisted state)")
    print("Synthesis occurs exactly once semantically across restart: PASS")


# ============================================================ SECTION 18 ==
def test_f6_why_what_how_reconstructible_from_stored_evidence(federation_setup):
    """After synthesis, every WHY/WHAT/HOW question (mission section 18)
    must be answerable from STORED evidence alone -- this test runs the
    mission once, then answers each question using ONLY store queries
    (get_registry_entry, get_state_events, get_institutional_report,
    get_provenance_record), never re-deriving from the live subprocess
    results dict."""
    store, db_path = federation_setup
    env_base = _env_base(db_path)

    dat_ai_result = _seed_real_dat_ai_trigger(env_base)
    result_a = _run("process_a_nexus_trigger_and_route.py", env_base)
    lib_deleg = next(d for d in result_a["delegations_created"] if d["recipient"] == "librarian")
    sen_deleg = next(d for d in result_a["delegations_created"] if d["recipient"] == "sentinel")

    env_b = env_base.copy()
    env_b["MISSION_ID"] = lib_deleg["mission_id"]
    env_b["DELEGATION_ID"] = lib_deleg["delegation_id"]
    result_b = _run("process_b_librarian_research.py", env_b)

    env_c = env_base.copy()
    env_c["MISSION_ID"] = sen_deleg["mission_id"]
    env_c["DELEGATION_ID"] = sen_deleg["delegation_id"]
    env_c["SENTINEL_DB_PATH"] = REAL_SENTINEL_DB
    result_c = _run("process_c_sentinel_analysis.py", env_c)

    env_d = env_base.copy()
    env_d["TRIGGER_ID"] = result_a["trigger_id"]
    env_d["LIBRARIAN_REPORT_ID"] = result_b["report_id"]
    env_d["SENTINEL_REPORT_ID"] = result_c["report_id"]
    env_d["TRIGGER_EVIDENCE_REFS_JSON"] = json.dumps(dat_ai_result.get("provenance_ids", []))
    env_d["TRIGGER_PROVENANCE_REFS_JSON"] = json.dumps(dat_ai_result.get("provenance_ids", []))
    _run("process_d_nexus_synthesis.py", env_d)

    # ---- Reconstruction: STORE QUERIES ONLY from here down ----
    dat_ai_accepted = store.last_accepted_report("dat_ai")
    librarian_report = store.get_institutional_report(result_b["report_id"])
    sentinel_report = store.get_institutional_report(result_c["report_id"])
    nexus_events = store.get_state_events("nexus", capability_name="cross_domain_synthesis")

    answers = {}

    # WHAT did DAT.AI observe?
    answers["WHAT_DAT_AI_OBSERVED"] = dat_ai_accepted["report"]["findings"]
    assert answers["WHAT_DAT_AI_OBSERVED"], "must be reconstructible"

    # WHY did NEXUS investigate this? (the delegation's own `reason` field,
    # persisted in delegation_log -- reconstructed via all_delegations())
    all_delegations = store.all_delegations()
    lib_delegation_row = next(d for d in all_delegations if d.get("proposal_id") == lib_deleg["delegation_id"])
    answers["WHY_NEXUS_INVESTIGATED"] = lib_delegation_row["reason"]
    assert answers["WHY_NEXUS_INVESTIGATED"]

    # WHY was Librarian selected? WHY was Sentinel selected? (same
    # `reason` field, persisted per-delegation, one per recipient)
    sen_delegation_row = next(d for d in all_delegations if d.get("proposal_id") == sen_deleg["delegation_id"])
    answers["WHY_LIBRARIAN_SELECTED"] = lib_delegation_row["reason"]
    answers["WHY_SENTINEL_SELECTED"] = sen_delegation_row["reason"]
    assert "librarian" in answers["WHY_LIBRARIAN_SELECTED"].lower() or "research" in answers["WHY_LIBRARIAN_SELECTED"].lower()
    assert "sentinel" in answers["WHY_SENTINEL_SELECTED"].lower() or "market" in answers["WHY_SENTINEL_SELECTED"].lower()

    # WHAT evidence did Librarian find?
    answers["WHAT_LIBRARIAN_EVIDENCE"] = librarian_report["evidence_refs"]
    assert answers["WHAT_LIBRARIAN_EVIDENCE"]

    # WHAT financial evidence did Sentinel use?
    answers["WHAT_SENTINEL_EVIDENCE"] = sentinel_report["evidence_refs"]
    assert answers["WHAT_SENTINEL_EVIDENCE"]

    # WHERE did they disagree? (from the persisted synthesis transition_reason)
    answers["WHERE_DISAGREEMENT"] = nexus_events[-1]["transition_reason"]

    # HOW was the executive conclusion derived?
    answers["HOW_CONCLUSION_DERIVED"] = nexus_events[-1]["new_lifecycle"]
    assert answers["HOW_CONCLUSION_DERIVED"] in (
        "SUPPORTED_CROSS_DOMAIN_INFERENCE", "PARTIALLY_SUPPORTED", "MIXED_EVIDENCE",
        "CONTRADICTORY_EVIDENCE", "INSUFFICIENT_EVIDENCE",
        "NO_MATERIAL_CROSS_DOMAIN_EFFECT_ESTABLISHED",
    )

    # WHAT remains unknown? (Librarian's + Sentinel's own limitations,
    # persisted verbatim in their reports)
    answers["WHAT_REMAINS_UNKNOWN"] = librarian_report["limitations"] + sentinel_report["limitations"]
    assert answers["WHAT_REMAINS_UNKNOWN"]

    print("\n=== F6 WHY/WHAT/HOW RECONSTRUCTION (Section 18) ===")
    for q, a in answers.items():
        preview = a if isinstance(a, str) else f"{len(a)} item(s): {a[0][:80]}..." if a else "EMPTY"
        print(f"{q}: {preview}")
    print("All questions answered from stored evidence alone, no rerun: PASS")
