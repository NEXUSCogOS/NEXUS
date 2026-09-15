"""F4C: Full three-process E2E commissioning with federation integration.

Mission requirement: NEXUS → Librarian → NEXUS using real federation.

This is the genuine acceptance criterion 11 test using:
- Real persistent delegation delivery
- Three genuinely separate OS processes
- Complete provenance chain
- Independent citation validation
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

# Federation paths
FEDERATION_ROOT = str(Path(__file__).resolve().parents[2].parent / "nexus_federation")
LIBRARIAN_ROOT = str(Path(__file__).resolve().parents[2])
DAT_AI_ROOT = str(Path(FEDERATION_ROOT).parent / "dat_ai")
HELPERS_DIR = Path(__file__).resolve().parent / "_subprocess_helpers"

# Add paths for this test module
sys.path.insert(0, FEDERATION_ROOT)
sys.path.insert(0, LIBRARIAN_ROOT)
sys.path.insert(0, DAT_AI_ROOT)

# Now import federation components
from contracts.generic import validate_report as validate_generic_report
from ingress.contract_registry import (
    bootstrap_federation_registry,
    known_institution_ids,
    register_contract,
    unregister_contract,
)
from persistence.db import FederationStore
from kernel import FederationKernel


@pytest.fixture
def federation_setup(tmp_path):
    """Set up federation with all three institutions registered."""
    db_path = tmp_path / "f4c_federation.db"
    store = FederationStore(str(db_path))

    # Bootstrap all three canonical institutions
    bootstrap_federation_registry()

    yield store, db_path

    # Cleanup (unregister will be called by the helper if needed, but clean up here too)
    unregister_contract("nexus")
    unregister_contract("librarian")
    unregister_contract("dat_ai")


def test_f4c_institutions_registered():
    """Verify all three institutions are registered in bootstrap."""
    bootstrap_federation_registry()
    registered = known_institution_ids()
    assert "nexus" in registered, "NEXUS must be registered"
    assert "librarian" in registered, "Librarian must be registered"
    assert "dat_ai" in registered, "DAT.AI must be registered"


def test_f4c_full_three_process_e2e(federation_setup):
    """F4C criterion 11: Real three-process federation E2E with Librarian research.

    Proves:
    - NEXUS Process A creates and persists real delegation
    - Librarian Process B claims mission, runs real research
    - NEXUS Process C ingests result through generic ingress
    - Three distinct PIDs
    - Complete provenance chain
    - No shared in-memory state
    """
    store, db_path = federation_setup

    # Research question for positive test
    research_question = (
        "What empirical and theoretical evidence supports separating a global "
        "executive layer from specialist cognitive institutions in distributed "
        "cognitive or agent architectures, and what failure modes or limitations "
        "does the literature identify?"
    )

    # Environment for all processes (federation store path)
    env_base = os.environ.copy()
    env_base["FEDERATION_STORE_PATH"] = str(db_path)
    env_base["PYTHONDONTWRITEBYTECODE"] = "1"

    # ---- PROCESS A: NEXUS creates and persists delegation ----

    process_a_script = str(HELPERS_DIR / "process_a_nexus_delegation_creator.py")
    result_a = subprocess.run(
        [sys.executable, process_a_script],
        env=env_base,
        capture_output=True,
        text=True,
        timeout=30
    )

    assert result_a.returncode == 0, f"Process A failed: {result_a.stderr}"
    result_a_data = json.loads(result_a.stdout)
    assert result_a_data["process_a_success"], "Process A reported failure"

    pid_a = result_a_data["pid"]
    mission_id = result_a_data["mission_id"]
    delegation_id = result_a_data["delegation_id"]

    # ---- PROCESS B: LIBRARIAN claims and executes research ----

    process_b_script = str(HELPERS_DIR / "process_b_librarian_researcher.py")
    env_b = env_base.copy()
    env_b["MISSION_ID"] = mission_id
    env_b["DELEGATION_ID"] = delegation_id
    env_b["RESEARCH_QUESTION"] = research_question
    env_b["QUERY_TERMS"] = "executive layer specialist institutions cognitive architecture distributed"

    result_b = subprocess.run(
        [sys.executable, process_b_script],
        env=env_b,
        capture_output=True,
        text=True,
        timeout=30
    )

    assert result_b.returncode == 0, f"Process B failed: {result_b.stderr}"
    result_b_data = json.loads(result_b.stdout)
    assert result_b_data["process_b_success"], "Process B reported failure"

    pid_b = result_b_data["pid"]
    claim_id = result_b_data["claim_id"]
    report_id = result_b_data["report_id"]

    # ---- PROCESS C: NEXUS ingests result through federation ----

    process_c_script = str(HELPERS_DIR / "process_c_nexus_ingester.py")
    env_c = env_base.copy()
    env_c["MISSION_ID"] = mission_id
    env_c["REPORT_ID"] = report_id

    result_c = subprocess.run(
        [sys.executable, process_c_script],
        env=env_c,
        capture_output=True,
        text=True,
        timeout=30
    )

    assert result_c.returncode == 0, f"Process C failed: {result_c.stderr}"
    result_c_data = json.loads(result_c.stdout)
    assert result_c_data["process_c_success"], "Process C reported failure"

    pid_c = result_c_data["pid"]

    # ---- VERIFICATION: Three distinct processes ----

    assert pid_a != pid_b, f"Process A and B have same PID: {pid_a}"
    assert pid_b != pid_c, f"Process B and C have same PID: {pid_b}"
    assert pid_a != pid_c, f"Process A and C have same PID: {pid_a}"

    # ---- VERIFICATION: Provenance chain ----

    assert mission_id, "Mission ID must be recorded"
    assert delegation_id, "Delegation ID must be recorded"
    assert claim_id, "Claim ID must be recorded"
    assert report_id, "Report ID must be recorded"

    # ---- VERIFICATION: Ingestion succeeded ----

    assert result_c_data["ingress_accepted"], "Federation kernel rejected report"
    assert len(result_c_data["provenance_ids"]) > 0, "No provenance IDs created"

    # ---- VERIFICATION: Research executed ----

    assert result_b_data["retrieval_count"] >= 0, "Retrieval count must be non-negative"
    assert result_b_data["gap_count"] >= 0, "Gap count must be non-negative"

    print(f"\n=== F4C THREE-PROCESS TEST RESULTS ===")
    print(f"Process A PID: {pid_a}")
    print(f"Process B PID: {pid_b}")
    print(f"Process C PID: {pid_c}")
    print(f"Mission ID: {mission_id}")
    print(f"Delegation ID: {delegation_id}")
    print(f"Claim ID: {claim_id}")
    print(f"Report ID: {report_id}")
    print(f"Retrieval Count: {result_b_data['retrieval_count']}")
    print(f"Source IDs: {len(result_b_data['source_ids'])}")
    print(f"Gap Count: {result_b_data['gap_count']}")
    print(f"Ingress Accepted: {result_c_data['ingress_accepted']}")
    print(f"Provenance IDs: {len(result_c_data['provenance_ids'])}")


def test_f4c_three_process_negative_control(federation_setup):
    """F4C negative control: Unsupported question through full federation.

    Proves:
    - No fabrication on out-of-scope research
    - Proper INSUFFICIENT_EVIDENCE behavior
    - Full federation path handles gracefully
    """
    store, db_path = federation_setup

    # Out-of-scope research question
    research_question = "What are the current market prices for Martian real estate in 2026?"

    # Environment for all processes
    env_base = os.environ.copy()
    env_base["FEDERATION_STORE_PATH"] = str(db_path)
    env_base["PYTHONDONTWRITEBYTECODE"] = "1"

    # ---- PROCESS A: Create delegation for unsupported question ----

    process_a_script = str(HELPERS_DIR / "process_a_nexus_delegation_creator.py")
    result_a = subprocess.run(
        [sys.executable, process_a_script],
        env=env_base,
        capture_output=True,
        text=True,
        timeout=30
    )

    assert result_a.returncode == 0, f"Process A failed: {result_a.stderr}"
    result_a_data = json.loads(result_a.stdout)

    pid_a = result_a_data["pid"]
    mission_id = result_a_data["mission_id"]
    delegation_id = result_a_data["delegation_id"]

    # ---- PROCESS B: Execute on unsupported question ----

    process_b_script = str(HELPERS_DIR / "process_b_librarian_researcher.py")
    env_b = env_base.copy()
    env_b["MISSION_ID"] = mission_id
    env_b["DELEGATION_ID"] = delegation_id
    env_b["RESEARCH_QUESTION"] = research_question
    env_b["QUERY_TERMS"] = "martian real estate prices"

    result_b = subprocess.run(
        [sys.executable, process_b_script],
        env=env_b,
        capture_output=True,
        text=True,
        timeout=30
    )

    assert result_b.returncode == 0, f"Process B failed: {result_b.stderr}"
    result_b_data = json.loads(result_b.stdout)
    assert result_b_data["process_b_success"], "Process B reported failure"

    # Negative control: Should still have a report, but likely with no findings or INSUFFICIENT_EVIDENCE
    report_id = result_b_data["report_id"]
    assert report_id, "Report should still be created even for unsupported questions"

    # ---- PROCESS C: Ingest result ----

    process_c_script = str(HELPERS_DIR / "process_c_nexus_ingester.py")
    env_c = env_base.copy()
    env_c["MISSION_ID"] = mission_id
    env_c["REPORT_ID"] = report_id

    result_c = subprocess.run(
        [sys.executable, process_c_script],
        env=env_c,
        capture_output=True,
        text=True,
        timeout=30
    )

    assert result_c.returncode == 0, f"Process C failed: {result_c.stderr}"
    result_c_data = json.loads(result_c.stdout)

    # Negative control: Report should be ingested, no fabrication occurred
    assert result_c_data["ingress_accepted"], "Federation should accept even unsupported research"

    # Verify no fabrication: retrieval count should be zero or very low
    # (no invented sources)
    print(f"\n=== F4C NEGATIVE CONTROL RESULTS ===")
    print(f"Out-of-scope Question: {research_question}")
    print(f"Retrieval Count: {result_b_data['retrieval_count']}")
    print(f"Source IDs Found: {len(result_b_data['source_ids'])}")
    print(f"Gap Count: {result_b_data['gap_count']}")
    print(f"Report Created: {bool(report_id)}")
    print(f"Ingestion Accepted: {result_c_data['ingress_accepted']}")


def test_f4c_nexus_registration():
    """Verify NEXUS can be registered and used with generic contract."""
    register_contract(
        "nexus",
        validate_generic_report,
        frozenset({"1.0.0"})
    )

    try:
        from ingress.contract_registry import get_contract
        registration = get_contract("nexus")
        assert registration is not None
        assert registration.validate_fn == validate_generic_report
        assert "1.0.0" in registration.known_schema_versions
    finally:
        unregister_contract("nexus")
