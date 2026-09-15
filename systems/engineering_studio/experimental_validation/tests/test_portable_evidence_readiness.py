import hashlib
import json
from pathlib import Path

from experimental_validation.gate_validator import (
    _resolve_evidence_path,
    validate_gate_record,
)
from experimental_validation.readiness import (
    evaluate_experiment,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def _record(path, evidence_path):
    record = {
        "gate_id": "test-gate",
        "gate": "canonical test gate",
        "status": "PASS",
        "reviewer": "independent-test-reviewer",
        "verified_at": "2026-09-15T00:00:00Z",
        "contradictions_resolved": True,
        "evidence_refs": [
            {
                "path": "${NEXUS_ROOT}/evidence.txt",
                "sha256": _sha256(evidence_path),
            }
        ],
    }

    path.write_text(
        json.dumps(record)
    )


def test_portable_nexus_root_reference_resolves(tmp_path):
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("evidence")

    record = tmp_path / "test-gate.json"
    _record(record, evidence)

    result = validate_gate_record(
        record,
        {
            "gate_id": "test-gate",
            "canonical_gate_text":
                "canonical test gate",
        },
        nexus_root=tmp_path,
    )

    assert result["valid"] is True
    assert result["reasons"] == []
    assert len(
        result["validated_evidence_refs"]
    ) == 1


def test_portable_reference_requires_explicit_root(tmp_path):
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("evidence")

    record = tmp_path / "test-gate.json"
    _record(record, evidence)

    result = validate_gate_record(
        record,
        {
            "gate_id": "test-gate",
            "canonical_gate_text":
                "canonical test gate",
        },
    )

    assert result["valid"] is False

    assert any(
        "NEXUS_ROOT_REQUIRED" in reason
        for reason in result["reasons"]
    )


def test_portable_reference_cannot_escape_root(tmp_path):
    try:
        _resolve_evidence_path(
            "${NEXUS_ROOT}/../escape.txt",
            tmp_path,
        )
    except ValueError as exc:
        assert str(exc) == (
            "EVIDENCE_PATH_ESCAPES_NEXUS_ROOT"
        )
    else:
        raise AssertionError(
            "root escape accepted"
        )


def test_readiness_threads_nexus_root(tmp_path):
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("evidence")

    records = tmp_path / "records"
    records.mkdir()

    record = records / "test-gate.json"
    _record(record, evidence)

    requirement = {
        "experiment_id": "TEST-EXP",
        "registry_status": "BLOCKED",
        "required_gate_count": 1,
        "required_gates": [
            {
                "gate_id": "test-gate",
                "gate": "canonical test gate",
            }
        ],
    }

    result = evaluate_experiment(
        requirement,
        records,
        nexus_root=tmp_path,
    )

    assert result["verified_gate_count"] == 1
    assert result["unresolved_gate_count"] == 0
    assert result[
        "all_required_gates_verified"
    ] is True

    # Registry remains BLOCKED, so successful
    # gate validation only makes it eligible.
    assert result["authorization"] == (
        "READY_ELIGIBLE"
    )

    assert result[
        "registry_transition_performed"
    ] is False

    assert result[
        "execution_authorized"
    ] is False
