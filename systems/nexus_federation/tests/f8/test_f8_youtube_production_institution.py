"""F8: YouTube Production institution -- real cross-domain synthesis ->
real, bounded media production -> READY_FOR_PUBLICATION_AUTHORIZATION,
never PUBLISHED.

Three-process pipeline (mission section 24), fed by a FRESH real run of
F6's own four-process chain (real DAT.AI planning-zone data, real
Librarian + Sentinel analysis, real executive synthesis) -- reused
directly rather than re-derived, since it is already-proven, real,
non-fabricated machinery producing a genuinely suitable
(PARTIALLY_SUPPORTED) conclusion for this mission's defining experiment.
"""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest

FEDERATION_ROOT = str(Path(__file__).resolve().parents[2])
DAT_AI_ROOT = str(Path(FEDERATION_ROOT).parent / "dat_ai")
YOUTUBE_ROOT = str(Path(FEDERATION_ROOT).parent / "youtube_production")
SENTINEL_NEXUS_ROOT = str(Path(FEDERATION_ROOT).parent / "sentinel")
F6_HELPERS_DIR = Path(FEDERATION_ROOT) / "tests" / "f6" / "_subprocess_helpers"
F8_HELPERS_DIR = Path(__file__).resolve().parent / "_subprocess_helpers"
REAL_SENTINEL_DB = str(Path(SENTINEL_NEXUS_ROOT) / "financial_intelligence.db")

# Deliberately NOT inserting YOUTUBE_ROOT into sys.path at module scope,
# and NOT bare-importing youtube_production's own schema/storage/script/
# rights modules into this shared pytest process: news_intelligence ships
# its own same-named bare modules (schema.py, storage.py), and importing
# both under the bare name `schema`/`storage` in one process poisons
# sys.modules for whichever package's test collects second -- a real
# collision found and fixed during this mission's construction (it broke
# 5 of test_f7's own tests when both suites ran in the same pytest
# session). Every youtube_production-internal check below therefore runs
# in its OWN fresh subprocess, exactly like every other F8/F6/F7 check.
if FEDERATION_ROOT not in sys.path:
    sys.path.insert(0, FEDERATION_ROOT)
if DAT_AI_ROOT not in sys.path:
    sys.path.insert(0, DAT_AI_ROOT)

from ingress.contract_registry import bootstrap_federation_registry
from persistence.db import FederationStore
from authority.model import AuthorityLevel, exceeds_phase_ceiling
from budget.schema import ResourceBudget
from delegation.schema import DelegationProposal, RiskClass
from pydantic import ValidationError


def _find_mission_terminal_state(yt_db_path, production_mission_id) -> str:
    """Reads YouTube's mission table with a plain sqlite3 query -- not by
    importing youtube_production.storage's ORM-ish wrapper into this
    shared process (see the module-collision note above)."""
    conn = sqlite3.connect(str(yt_db_path))
    try:
        row = conn.execute(
            "SELECT terminal_state FROM production_missions WHERE production_mission_id = ?",
            (production_mission_id,),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


@pytest.fixture
def stores(tmp_path):
    fed_db = tmp_path / "f8_federation.db"
    yt_db = tmp_path / "f8_youtube_production.db"
    bootstrap_federation_registry()
    store = FederationStore(str(fed_db))
    yield store, fed_db, yt_db


def _run(helpers_dir, script_name, env, timeout=90):
    result = subprocess.run(
        [sys.executable, str(helpers_dir / script_name)],
        env=env, capture_output=True, text=True, timeout=timeout,
    )
    assert result.returncode == 0, (
        f"{script_name} failed (exit {result.returncode}):\n"
        f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )
    return json.loads(result.stdout)


def _env_base(fed_db, yt_db):
    env = os.environ.copy()
    env["FEDERATION_STORE_PATH"] = str(fed_db)
    env["YOUTUBE_DB_PATH"] = str(yt_db)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _run_real_f6_chain(env_base):
    """Re-runs F6's own real, already-proven four-process chain fresh,
    to obtain a genuinely current cross-domain synthesis. Not a fixture
    or a cached result -- a live re-execution of real code against real
    DAT.AI planning-zone data and the real Sentinel database."""
    dat_ai_result = _run(F6_HELPERS_DIR, "process_dat_ai_trigger_source.py", env_base)
    assert dat_ai_result["ingress_accepted"] is True

    result_a = _run(F6_HELPERS_DIR, "process_a_nexus_trigger_and_route.py", env_base)
    lib_deleg = next(d for d in result_a["delegations_created"] if d["recipient"] == "librarian")
    sen_deleg = next(d for d in result_a["delegations_created"] if d["recipient"] == "sentinel")

    env_b = env_base.copy()
    env_b["MISSION_ID"] = lib_deleg["mission_id"]
    env_b["DELEGATION_ID"] = lib_deleg["delegation_id"]
    result_b = _run(F6_HELPERS_DIR, "process_b_librarian_research.py", env_b)

    env_c = env_base.copy()
    env_c["MISSION_ID"] = sen_deleg["mission_id"]
    env_c["DELEGATION_ID"] = sen_deleg["delegation_id"]
    env_c["SENTINEL_DB_PATH"] = REAL_SENTINEL_DB
    result_c = _run(F6_HELPERS_DIR, "process_c_sentinel_analysis.py", env_c)

    env_d = env_base.copy()
    env_d["TRIGGER_ID"] = result_a["trigger_id"]
    env_d["LIBRARIAN_REPORT_ID"] = result_b["report_id"]
    env_d["SENTINEL_REPORT_ID"] = result_c["report_id"]
    env_d["TRIGGER_EVIDENCE_REFS_JSON"] = json.dumps(dat_ai_result.get("provenance_ids", []))
    env_d["TRIGGER_PROVENANCE_REFS_JSON"] = json.dumps(dat_ai_result.get("provenance_ids", []))
    result_d = _run(F6_HELPERS_DIR, "process_d_nexus_synthesis.py", env_d)

    return result_a, result_b, result_c, result_d


# =========================================================== SECTION 24/25 =
def test_f8_full_production_loop_real_synthesis(stores):
    """The defining F8 experiment: real synthesis -> real production
    mission -> real evidence pack/script/fact-check -> real render (say +
    Pillow + ffmpeg) -> real InstitutionalReport ingested through the
    generic kernel -> READY_FOR_PUBLICATION_AUTHORIZATION. Never
    PUBLISHED."""
    store, fed_db, yt_db = stores
    env_base = _env_base(fed_db, yt_db)

    result_a6, result_b6, result_c6, result_d6 = _run_real_f6_chain(env_base)

    conclusion_class = result_d6["executive_conclusion_class"]
    print(f"\nreal F6 executive_conclusion_class this run: {conclusion_class}")

    env_a8 = env_base.copy()
    env_a8["TRIGGER_ID"] = result_a6["trigger_id"]
    env_a8["SYNTHESIS_ID"] = result_d6["synthesis_id"]
    env_a8["EXECUTIVE_CONCLUSION_CLASS"] = conclusion_class
    env_a8["EXECUTIVE_CONCLUSION"] = result_d6["executive_conclusion"]
    env_a8["EVIDENCE_REFS_JSON"] = json.dumps(result_d6["evidence_refs"])
    env_a8["PROVENANCE_REFS_JSON"] = json.dumps(result_d6["provenance_refs"])
    env_a8["UNCERTAINTIES_JSON"] = json.dumps(result_d6["uncertainties"])
    env_a8["CONTRADICTORY_FINDINGS_JSON"] = json.dumps(result_d6["contradictory_findings"])
    env_a8["EVENT_HEADLINE"] = (
        "Vietnamese industrial-park and real-estate sector stocks near a "
        "government planning zone adjacent to Long Thanh International Airport"
    )
    env_a8["EVENT_KEYWORDS_JSON"] = json.dumps(["stocks", "market", "real estate", "investing", "trading"])

    result_a8 = _run(F8_HELPERS_DIR, "process_a_nexus_create_mission.py", env_a8)

    if not result_a8["suitable"]:
        pytest.skip(
            f"real F6 re-run this time produced executive_conclusion_class="
            f"{conclusion_class!r}, not editorially suitable -- see "
            f"test_f8_no_production_action_required_is_legitimate for this path"
        )

    production_mission_id = result_a8["production_mission_id"]
    assert result_a8["delegation_created"] is True
    assert result_a8["delegation_authority"] == "GENERATE_INTERNAL"

    if result_a8["terminal_state"] == "NO_APPROPRIATE_CHANNEL":
        pytest.skip("no configured channel identity matched this real event's editorial content -- legitimate NO_APPROPRIATE_CHANNEL outcome")

    env_b8 = env_base.copy()
    env_b8["PRODUCTION_MISSION_ID"] = production_mission_id
    env_b8["SOURCE_EVENT_REF"] = result_a6["trigger_id"]
    env_b8["SUPPORTING_FINDINGS_JSON"] = json.dumps(result_d6["supporting_findings"])
    env_b8["CONTRADICTORY_FINDINGS_JSON"] = json.dumps(result_d6["contradictory_findings"])
    env_b8["UNCERTAINTIES_JSON"] = json.dumps(result_d6["uncertainties"])
    env_b8["TEMPORAL_MISMATCHES_JSON"] = json.dumps(result_d6["temporal_mismatches"])
    env_b8["SPECIALIST_REPORT_IDS_JSON"] = json.dumps(result_d6["input_report_ids"])
    env_b8["EXECUTIVE_CONCLUSION_CLASS"] = conclusion_class

    result_b8 = _run(F8_HELPERS_DIR, "process_b_youtube_production.py", env_b8, timeout=120)

    assert result_b8["ingress_accepted"] is True
    assert result_b8["terminal_state"] == "READY_FOR_PUBLICATION_AUTHORIZATION"
    assert Path(result_b8["output_path"]).exists(), "render output must be a real file on disk"
    assert result_b8["duration_seconds"] > 0, "render must have a real, positive duration"
    assert len(result_b8["output_hash"]) == 64, "output_hash must be a real sha256 hex digest"

    env_c8 = env_base.copy()
    env_c8["PRODUCTION_MISSION_ID"] = production_mission_id
    result_c8 = _run(F8_HELPERS_DIR, "process_c_nexus_ingest.py", env_c8)

    assert result_c8["final_terminal_state"] == "READY_FOR_PUBLICATION_AUTHORIZATION"
    assert result_c8["publication_component_lifecycle"] == "NOT_COMMISSIONED"

    pids = {result_a8["pid"], result_b8["pid"], result_c8["pid"]}
    assert len(pids) == 3, "all three F8 processes must have distinct PIDs"

    assert _find_mission_terminal_state(yt_db, production_mission_id) == "READY_FOR_PUBLICATION_AUTHORIZATION"

    print(f"production_mission_id={production_mission_id}")
    print(f"render output_hash={result_b8['output_hash']} path={result_b8['output_path']} duration={result_b8['duration_seconds']}s")
    print(f"PID_A={result_a8['pid']} PID_B={result_b8['pid']} PID_C={result_c8['pid']}")


# ======================================================== SECTION 26 (MANDATORY) =
def test_f8_publication_rejection_mandatory(stores):
    """A delegation requesting publication authority (EXTERNAL_ACTION,
    exactly what 'publish this video to YouTube' requires) must be
    structurally rejected before any specialist code runs -- the SAME
    mechanism (authority/model.py's phase-ceiling validator) that already
    blocks every authority level above GENERATE_INTERNAL for this
    federation."""
    assert exceeds_phase_ceiling(AuthorityLevel.EXTERNAL_ACTION) is True
    assert exceeds_phase_ceiling(AuthorityLevel.HIGH_CONSEQUENCE_ACTION) is True
    assert exceeds_phase_ceiling(AuthorityLevel.GENERATE_INTERNAL) is False

    rejected = False
    rejection_reason = None
    try:
        DelegationProposal(
            mission_id="publish-attempt-mission",
            proposal_id=str(uuid5(NAMESPACE_URL, "f8-publish-attempt")),
            recipient="youtube_production",
            objective="Publish this video to YouTube",
            reason="attempted publication request -- must be rejected",
            evidence_refs=[],
            priority=1,
            authority=AuthorityLevel.EXTERNAL_ACTION,
            constraints=[],
            resource_budget=ResourceBudget(
                cpu_seconds=1.0, memory_bytes=1, elapsed_seconds=1.0,
                local_storage_bytes=0, external_storage_bytes=0,
                api_cost_usd=0.0, model_tokens=0, basis="rejection test",
            ),
            risk_class=RiskClass.HIGH,
            parent_mission="test",
            idempotency_key="publish-attempt-key",
        )
    except ValidationError as e:
        rejected = True
        rejection_reason = str(e)

    assert rejected, "AUTHORITY_REJECTED: a publication-authority delegation must never construct successfully"
    assert "exceeds the phase ceiling" in rejection_reason

    # Evidence that no upload path was ever touched by this attempt: this
    # package (youtube_production/) contains no import of googleapiclient
    # or the pre-existing youtube_uploader.py anywhere.
    package_root = Path(YOUTUBE_ROOT)
    offending = []
    for py_file in package_root.glob("*.py"):
        text = py_file.read_text()
        if "googleapiclient" in text or "youtube_uploader" in text or "MediaFileUpload" in text:
            offending.append(str(py_file))
    assert offending == [], f"AUTHORITY_REJECTED evidence violated -- upload-capable code referenced in: {offending}"

    print("\nAUTHORITY_REJECTED: publication delegation construction raised ValidationError, no upload API referenced anywhere in youtube_production/")


# =========================================================== SECTION 27 =
def test_f8_unsupported_claim_negative_control():
    """Fixture-only, per this mission's own allowance for negative
    controls: an evidence pack whose only real finding establishes
    NOTHING (NO_MATERIAL_CROSS_DOMAIN_EFFECT_ESTABLISHED-equivalent), and
    a script that attempts to smuggle in a sensational, unbacked FACT
    claim (claim_id with no matching evidence item). The fact-check stage
    must remove it, never silently pass it through to the final script.

    Run as its own subprocess (see the module-collision note near the
    top of this file) rather than importing youtube_production's own
    schema/script modules into this shared pytest process."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = _run(F8_HELPERS_DIR, "process_unsupported_claim_check.py", env)

    unsupported_count = sum(1 for o in result["outcomes"] if o == "UNSUPPORTED")
    assert unsupported_count == 1
    assert "REMOVED" in result["actions_taken"]
    assert "sensational_claim" not in result["kept_segment_ids"], "the unsupported sensational claim must not survive into the final script"
    assert "intro" in result["kept_segment_ids"]

    print("\nunsupported sensational claim correctly REMOVED before render acceptance")


# =========================================================== SECTION 28 =
def test_f8_missing_rights_negative_control():
    """An asset whose rights were never established (rights_status=
    UNKNOWN) must be excluded from the usable set, never silently
    treated as usable. Run as its own subprocess for the same reason as
    the unsupported-claim negative control above."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = _run(F8_HELPERS_DIR, "process_missing_rights_check.py", env)

    assert "stock-footage-asset-1" in result["blocked_ids"]
    assert "stock-footage-asset-1" not in result["usable_ids"]
    assert "voice-asset-1" in result["usable_ids"]
    assert result["unknown_usable_flag"] is False
    assert result["unknown_rights_status"] == "UNKNOWN"

    print(f"\nUNKNOWN-rights asset correctly blocked: {result['blocked_ids']} blocked, {result['usable_ids']} usable")


# =========================================================== SECTION 29 =
def test_f8_idempotency_same_mission_replay(stores):
    """Replaying Process A against the SAME synthesis_id/trigger_id must
    not create a duplicate mission or duplicate delegation. Replaying
    Process B against the SAME production_mission_id with the SAME
    script revision must not create a duplicate render."""
    store, fed_db, yt_db = stores
    env_base = _env_base(fed_db, yt_db)

    result_a6, result_b6, result_c6, result_d6 = _run_real_f6_chain(env_base)
    conclusion_class = result_d6["executive_conclusion_class"]

    env_a8 = env_base.copy()
    env_a8["TRIGGER_ID"] = result_a6["trigger_id"]
    env_a8["SYNTHESIS_ID"] = result_d6["synthesis_id"]
    env_a8["EXECUTIVE_CONCLUSION_CLASS"] = conclusion_class
    env_a8["EXECUTIVE_CONCLUSION"] = result_d6["executive_conclusion"]
    env_a8["EVIDENCE_REFS_JSON"] = json.dumps(result_d6["evidence_refs"])
    env_a8["PROVENANCE_REFS_JSON"] = json.dumps(result_d6["provenance_refs"])
    env_a8["UNCERTAINTIES_JSON"] = json.dumps(result_d6["uncertainties"])
    env_a8["CONTRADICTORY_FINDINGS_JSON"] = json.dumps(result_d6["contradictory_findings"])
    env_a8["EVENT_HEADLINE"] = "Vietnamese industrial-park and real-estate sector stocks near a government planning zone"
    env_a8["EVENT_KEYWORDS_JSON"] = json.dumps(["stocks", "market", "real estate", "investing", "trading"])

    result_a8_run1 = _run(F8_HELPERS_DIR, "process_a_nexus_create_mission.py", env_a8)
    if not result_a8_run1["suitable"]:
        pytest.skip(f"real F6 re-run produced {conclusion_class!r}, not suitable this time")

    result_a8_run2 = _run(F8_HELPERS_DIR, "process_a_nexus_create_mission.py", env_a8)

    assert result_a8_run1["production_mission_id"] == result_a8_run2["production_mission_id"], "replay must reproduce the identical deterministic mission id"
    assert result_a8_run1["delegation_created"] is True
    assert result_a8_run2["delegation_created"] is False, "replay must recognize the existing delegation, not create a second one"
    assert result_a8_run2["mission_newly_created"] is False

    if result_a8_run1["terminal_state"] == "NO_APPROPRIATE_CHANNEL":
        pytest.skip("NO_APPROPRIATE_CHANNEL this run -- idempotency of mission/delegation creation already proven above")

    production_mission_id = result_a8_run1["production_mission_id"]
    env_b8 = env_base.copy()
    env_b8["PRODUCTION_MISSION_ID"] = production_mission_id
    env_b8["SOURCE_EVENT_REF"] = result_a6["trigger_id"]
    env_b8["SUPPORTING_FINDINGS_JSON"] = json.dumps(result_d6["supporting_findings"])
    env_b8["CONTRADICTORY_FINDINGS_JSON"] = json.dumps(result_d6["contradictory_findings"])
    env_b8["UNCERTAINTIES_JSON"] = json.dumps(result_d6["uncertainties"])
    env_b8["TEMPORAL_MISMATCHES_JSON"] = json.dumps(result_d6["temporal_mismatches"])
    env_b8["SPECIALIST_REPORT_IDS_JSON"] = json.dumps(result_d6["input_report_ids"])
    env_b8["EXECUTIVE_CONCLUSION_CLASS"] = conclusion_class

    result_b8_run1 = _run(F8_HELPERS_DIR, "process_b_youtube_production.py", env_b8, timeout=120)
    result_b8_run2 = _run(F8_HELPERS_DIR, "process_b_youtube_production.py", env_b8, timeout=120)

    assert result_b8_run1["render_newly_created"] is True
    assert result_b8_run2["render_newly_created"] is False, "same script revision replay must not create a duplicate render"
    assert result_b8_run1["render_id"] == result_b8_run2["render_id"]
    assert result_b8_run1["output_hash"] == result_b8_run2["output_hash"], "identical inputs must reproduce the identical output artifact"
    assert result_b8_run2["pack_reused"] is True
    assert result_b8_run2["script_reused"] is True

    print(f"\nidempotency proven: mission/delegation/render all stable across replay for {production_mission_id}")


# =========================================================== SECTION 30 =
def test_f8_recovery_after_partial_completion(stores):
    """A fresh Process B invocation, pointed at a production_mission_id
    whose evidence pack and script were ALREADY built (e.g. by a prior
    Process B that crashed after those steps), must resume from that
    persisted state rather than rebuilding it or corrupting the record."""
    store, fed_db, yt_db = stores
    env_base = _env_base(fed_db, yt_db)

    result_a6, result_b6, result_c6, result_d6 = _run_real_f6_chain(env_base)
    conclusion_class = result_d6["executive_conclusion_class"]

    env_a8 = env_base.copy()
    env_a8["TRIGGER_ID"] = result_a6["trigger_id"]
    env_a8["SYNTHESIS_ID"] = result_d6["synthesis_id"]
    env_a8["EXECUTIVE_CONCLUSION_CLASS"] = conclusion_class
    env_a8["EXECUTIVE_CONCLUSION"] = result_d6["executive_conclusion"]
    env_a8["EVIDENCE_REFS_JSON"] = json.dumps(result_d6["evidence_refs"])
    env_a8["PROVENANCE_REFS_JSON"] = json.dumps(result_d6["provenance_refs"])
    env_a8["UNCERTAINTIES_JSON"] = json.dumps(result_d6["uncertainties"])
    env_a8["CONTRADICTORY_FINDINGS_JSON"] = json.dumps(result_d6["contradictory_findings"])
    env_a8["EVENT_HEADLINE"] = "Vietnamese industrial-park and real-estate sector stocks near a government planning zone"
    env_a8["EVENT_KEYWORDS_JSON"] = json.dumps(["stocks", "market", "real estate", "investing", "trading"])

    result_a8 = _run(F8_HELPERS_DIR, "process_a_nexus_create_mission.py", env_a8)
    if not result_a8["suitable"] or result_a8["terminal_state"] == "NO_APPROPRIATE_CHANNEL":
        pytest.skip(f"real F6 re-run produced {conclusion_class!r} / no channel match this time -- not usable for this recovery test")

    production_mission_id = result_a8["production_mission_id"]

    env_b8 = env_base.copy()
    env_b8["PRODUCTION_MISSION_ID"] = production_mission_id
    env_b8["SOURCE_EVENT_REF"] = result_a6["trigger_id"]
    env_b8["SUPPORTING_FINDINGS_JSON"] = json.dumps(result_d6["supporting_findings"])
    env_b8["CONTRADICTORY_FINDINGS_JSON"] = json.dumps(result_d6["contradictory_findings"])
    env_b8["UNCERTAINTIES_JSON"] = json.dumps(result_d6["uncertainties"])
    env_b8["TEMPORAL_MISMATCHES_JSON"] = json.dumps(result_d6["temporal_mismatches"])
    env_b8["SPECIALIST_REPORT_IDS_JSON"] = json.dumps(result_d6["input_report_ids"])
    env_b8["EXECUTIVE_CONCLUSION_CLASS"] = conclusion_class

    # Simulate "crashed after evidence pack + script, before render": a
    # real, separate Process B invocation that deliberately stops right
    # after persisting the evidence pack + script (see
    # process_b_youtube_production.py's F8_STOP_AFTER_SCRIPT hook).
    env_b8_crash = env_b8.copy()
    env_b8_crash["F8_STOP_AFTER_SCRIPT"] = "1"
    crashed_result = _run(F8_HELPERS_DIR, "process_b_youtube_production.py", env_b8_crash)
    assert crashed_result["stopped_after_script"] is True

    # A FRESH Process B invocation, no crash flag, minimal env (does NOT
    # re-supply SUPPORTING_FINDINGS_JSON etc. -- a real resumed worker
    # must not need them again, since the evidence pack already exists
    # on disk).
    env_b8_resume = env_base.copy()
    env_b8_resume["PRODUCTION_MISSION_ID"] = production_mission_id
    env_b8_resume["EXECUTIVE_CONCLUSION_CLASS"] = conclusion_class

    result_b8 = _run(F8_HELPERS_DIR, "process_b_youtube_production.py", env_b8_resume, timeout=120)

    assert result_b8["pack_reused"] is True, "recovery must reuse the already-persisted evidence pack, not rebuild it"
    assert result_b8["script_reused"] is True, "recovery must reuse the already-persisted script, not rebuild it"
    assert result_b8["terminal_state"] == "READY_FOR_PUBLICATION_AUTHORIZATION"
    assert Path(result_b8["output_path"]).exists()

    print(f"\nrecovery proven: fresh Process B resumed from persisted evidence pack + script for {production_mission_id}")
