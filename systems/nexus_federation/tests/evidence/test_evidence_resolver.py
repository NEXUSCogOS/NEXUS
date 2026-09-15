"""EVIDENCE tests: real filesystem resolution and drift detection."""

from __future__ import annotations

from pathlib import Path

from evidence.resolver import (
    detect_drift,
    looks_like_commit_reference,
    resolve_evidence_ref,
)


def test_resolves_a_real_canonical_dat_ai_file():
    r = resolve_evidence_ref("docs/DATAI_CHARTER.md")
    assert r.resolved is True
    assert r.resolved_root == "dat_ai_canonical"
    assert r.sha256 is not None


def test_resolves_a_real_audit_trail_document():
    r = resolve_evidence_ref("DATAI_CANONICAL_TEST_BASELINE.md")
    assert r.resolved is True
    assert r.resolved_root == "engineering_studio_audit_trail"


def test_missing_evidence_reports_unresolved_not_an_exception():
    r = resolve_evidence_ref("this_file_definitely_does_not_exist_anywhere.md")
    assert r.resolved is False
    assert r.syntactically_valid is True
    assert "not found" in r.reason


def test_empty_ref_is_syntactically_invalid():
    r = resolve_evidence_ref("")
    assert r.syntactically_valid is False
    assert r.resolved is False


def test_null_byte_ref_is_syntactically_invalid():
    r = resolve_evidence_ref("some\x00thing")
    assert r.syntactically_valid is False


def test_drift_detection_no_baseline_means_no_drift_reported():
    r = resolve_evidence_ref("docs/DATAI_CHARTER.md")
    assert detect_drift(r, previously_recorded_sha256=None) is None


def test_drift_detection_same_hash_means_no_drift():
    r = resolve_evidence_ref("docs/DATAI_CHARTER.md")
    assert detect_drift(r, previously_recorded_sha256=r.sha256) is None


def test_drift_detection_different_hash_flags_drift():
    r = resolve_evidence_ref("docs/DATAI_CHARTER.md")
    fake_old_hash = "0" * 64
    drift = detect_drift(r, previously_recorded_sha256=fake_old_hash)
    assert drift is not None
    assert "changed" in drift


def test_corrupted_evidence_simulated_via_tmp_file(tmp_path: Path):
    """Simulates 'corrupted evidence' by resolving a file, then modifying
    it, then resolving again -- proves the resolver would detect the
    change (this is the drift-detection mechanism exercised end-to-end
    rather than against a fixed canonical file)."""
    f = tmp_path / "evidence.md"
    f.write_text("original content")
    r1 = resolve_evidence_ref(str(f), search_roots=[("tmp", tmp_path.parent)])
    assert r1.resolved is True
    hash1 = r1.sha256

    f.write_text("corrupted content")
    r2 = resolve_evidence_ref(str(f), search_roots=[("tmp", tmp_path.parent)])
    assert r2.resolved is True
    hash2 = r2.sha256

    assert hash1 != hash2
    drift = detect_drift(r2, previously_recorded_sha256=hash1)
    assert drift is not None


def test_looks_like_commit_reference_extracts_hash():
    ref = "NEXUS_LOCAL donor commit eb9ed1c (systems/dat_ai)"
    assert looks_like_commit_reference(ref) == "eb9ed1c"


def test_looks_like_commit_reference_returns_none_for_unstructured_text():
    ref = "a general statement about provenance with no hash in it"
    assert looks_like_commit_reference(ref) is None
