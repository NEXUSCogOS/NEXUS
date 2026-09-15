from __future__ import annotations

from hashlib import sha256
import json

import pytest

from runtime.hypothesis_evidence import EvidenceRecordRejected, append_evidence_relationship


def _record(source_path):
    return {
        "experiment_id": "NEXUS-EXP-004",
        "relationship": "CONTRADICTS",
        "source_identifier": "test:source-1",
        "source_title": "Independent contradictory finding",
        "source_path": str(source_path),
        "source_sha256": sha256(source_path.read_bytes()).hexdigest(),
        "citation": "Test Author (2026). Independent contradictory finding.",
        "passage_locator": "paragraph 1",
        "acquired_at": "2026-08-30T01:00:00+07:00",
        "verified_at": "2026-08-30T01:05:00+07:00",
        "reviewer": "independent-reviewer",
        "method_context": "controlled test fixture",
        "limitations": "fixture only",
        "confidence_basis": "source content and hash independently checked",
    }


def test_append_relationship_is_canonical_and_hash_chained(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("contradictory evidence", encoding="utf-8")
    ledger = tmp_path / "evidence.jsonl"
    first = append_evidence_relationship(_record(source), ledger_path=ledger)
    second_record = _record(source)
    second_record["relationship"] = "QUALIFIES"
    second_record["source_identifier"] = "test:source-2"
    second = append_evidence_relationship(second_record, ledger_path=ledger)
    assert second["previous_event_sha256"] == first["event_sha256"]
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 2


def test_missing_or_hash_mismatched_source_is_rejected(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("evidence", encoding="utf-8")
    record = _record(source)
    record["source_sha256"] = "0" * 64
    with pytest.raises(EvidenceRecordRejected, match="does not match"):
        append_evidence_relationship(record, ledger_path=tmp_path / "ledger.jsonl")


def test_unknown_experiment_id_is_rejected(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("evidence", encoding="utf-8")
    record = _record(source)
    record["experiment_id"] = "NEXUS-EXP-999"
    with pytest.raises(EvidenceRecordRejected, match="not canonical"):
        append_evidence_relationship(record, ledger_path=tmp_path / "ledger.jsonl")


def test_existing_ledger_tampering_fails_closed(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("evidence", encoding="utf-8")
    ledger = tmp_path / "ledger.jsonl"
    append_evidence_relationship(_record(source), ledger_path=ledger)
    event = json.loads(ledger.read_text(encoding="utf-8"))
    event["relationship"] = "CONFIRMS"
    ledger.write_text(json.dumps(event) + "\n", encoding="utf-8")
    with pytest.raises(EvidenceRecordRejected, match="ledger hash mismatch"):
        append_evidence_relationship(_record(source), ledger_path=ledger)
