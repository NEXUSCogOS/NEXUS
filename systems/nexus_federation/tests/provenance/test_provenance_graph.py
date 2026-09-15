"""Provenance model and multi-hop graph tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from provenance.graph import explain, root_verification_status, trace_back
from provenance.model import ProvenanceRecord, VerificationStatus


def _record(pid, source_type, parents=None, status=VerificationStatus.VERIFIED, method="test"):
    return ProvenanceRecord(
        provenance_id=pid,
        source_type=source_type,
        producer="test",
        method=method,
        parent_provenance_ids=parents or [],
        verification_status=status,
        verification_method="test-method" if status in (VerificationStatus.VERIFIED, VerificationStatus.INVALID) else None,
    )


def test_verified_requires_method():
    with pytest.raises(ValidationError):
        ProvenanceRecord(
            source_type="x",
            producer="p",
            method="m",
            verification_status=VerificationStatus.VERIFIED,
            verification_method=None,
        )


def test_unverified_does_not_require_method():
    rec = ProvenanceRecord(
        source_type="x", producer="p", method="m", verification_status=VerificationStatus.UNVERIFIED
    )
    assert rec.verification_method is None  # not fabricated


def test_multi_hop_trace_back_full_chain():
    """source_evidence -> institutional_report -> nexus_executive_state ->
    delegation_proposal, exactly the chain the mission names."""
    records = {
        "s1": _record("s1", "source_evidence_file"),
        "r1": _record("r1", "institutional_report", parents=["s1"]),
        "e1": _record("e1", "nexus_executive_state", parents=["r1"]),
        "d1": _record("d1", "delegation_proposal", parents=["e1"]),
    }
    lookup = lambda pid: records.get(pid)

    chain = trace_back("d1", lookup)
    assert [r.provenance_id for r in chain] == ["s1", "r1", "e1", "d1"]
    assert chain[0].source_type == "source_evidence_file"
    assert chain[-1].source_type == "delegation_proposal"


def test_trace_back_missing_record_returns_empty():
    assert trace_back("nonexistent", lambda pid: None) == []


def test_trace_back_is_cycle_safe():
    """A malformed cyclic graph (which should never occur, but must not
    hang the process if it does) terminates instead of looping forever."""
    records = {
        "a": _record("a", "x", parents=["b"]),
        "b": _record("b", "y", parents=["a"]),
    }
    lookup = lambda pid: records.get(pid)
    chain = trace_back("a", lookup)
    assert len(chain) == 2  # visits each once, does not loop


def test_explain_produces_readable_chain():
    records = {
        "s1": _record("s1", "source_evidence_file"),
        "r1": _record("r1", "institutional_report", parents=["s1"]),
    }
    lookup = lambda pid: records.get(pid)
    text = explain("r1", lookup)
    assert "source_evidence_file" in text
    assert "institutional_report" in text


def test_explain_unknown_id():
    text = explain("ghost", lambda pid: None)
    assert "no provenance record found" in text


def test_root_verification_status_reflects_ultimate_source_not_the_leaf():
    """A leaf record can be VERIFIED even though its ultimate source was
    only PARTIAL -- root_verification_status must report the ROOT's
    status, not the leaf's."""
    records = {
        "s1": _record("s1", "source_evidence_file", status=VerificationStatus.PARTIAL),
        "r1": _record("r1", "institutional_report", parents=["s1"], status=VerificationStatus.VERIFIED),
    }
    lookup = lambda pid: records.get(pid)
    assert root_verification_status("r1", lookup) == "PARTIAL"


def test_root_verification_status_missing_chain():
    assert root_verification_status("ghost", lambda pid: None) is None
