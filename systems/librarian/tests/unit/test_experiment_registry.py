from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.experiment_registry import (
    ExperimentExecutionDenied,
    RegistryValidationError,
    assess_experiment_readiness,
    load_and_validate_registry,
    require_experiment_authorisation,
    validate_reference_views,
)


def test_canonical_registry_and_both_reference_views_are_consistent():
    registry = load_and_validate_registry()
    validate_reference_views(registry)
    assert len(registry["experiments"]) == 6
    assert all(item["result_status"] == "BLOCKED" for item in registry["experiments"])


def test_blocked_experiment_is_denied_even_without_gate_evidence(tmp_path):
    decision = assess_experiment_readiness(
        "NEXUS-EXP-001", gate_evidence_dir=tmp_path
    )
    assert decision.authorised is False
    assert any("not READY" in reason for reason in decision.reasons)
    with pytest.raises(ExperimentExecutionDenied):
        require_experiment_authorisation("NEXUS-EXP-001", gate_evidence_dir=tmp_path)


def test_missing_provenance_source_fails_closed(tmp_path):
    registry = load_and_validate_registry(verify_source_basis=False)
    registry["canonical_path"] = str(tmp_path / "registry.json")
    registry["source_basis"][0]["path"] = str(tmp_path / "missing-source.md")
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(RegistryValidationError, match="source-basis file missing"):
        load_and_validate_registry(path)


def test_divergent_research_assistant_ids_fail_closed(tmp_path):
    registry = load_and_validate_registry()
    bad_link = {
        "registry_id": registry["registry_id"],
        "canonical_path": registry["canonical_path"],
        "experiment_ids": ["NEXUS-EXP-999"],
        "duplication_policy": "REFERENCE_ONLY_DO_NOT_COPY_RECORDS",
    }
    path = tmp_path / "bad-link.json"
    path.write_text(json.dumps(bad_link), encoding="utf-8")
    with pytest.raises(RegistryValidationError, match="experiment IDs diverged"):
        validate_reference_views(registry, [path])


def test_unverifiable_gate_artifact_is_denied(tmp_path):
    registry = load_and_validate_registry(verify_source_basis=False)
    registry["canonical_path"] = str(tmp_path / "registry.json")
    registry["experiments"][0]["result_status"] = "READY"
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    good_link = tmp_path / "link.json"
    good_link.write_text(json.dumps({
        "registry_id": registry["registry_id"],
        "canonical_path": registry["canonical_path"],
        "experiment_ids": [item["experiment_id"] for item in registry["experiments"]],
        "duplication_policy": "REFERENCE_ONLY_DO_NOT_COPY_RECORDS",
    }), encoding="utf-8")

    gate = registry["global_stability_gates"][0]
    (tmp_path / "global-01.json").write_text(
        json.dumps({
            "gate": gate,
            "status": "PASS",
            "reviewer": "independent-reviewer",
            "verified_at": "2026-08-30T00:00:00+07:00",
            "evidence_refs": [{"path": str(tmp_path / "missing.txt"), "sha256": "0" * 64}],
        }),
        encoding="utf-8",
    )
    decision = assess_experiment_readiness(
        "NEXUS-EXP-001", gate_evidence_dir=tmp_path, registry_path=path,
        link_paths=[good_link],
    )
    assert decision.authorised is False
    assert any("hash-mismatched" in reason for reason in decision.reasons)
