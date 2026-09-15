"""Fail-closed access and execution gating for the NEXUS experiment registry.

This module does not execute experiments.  It validates the sole canonical
registry, resolves the Librarian/Research Assistant reference views, verifies
provenance hashes, and issues a readiness decision that is DENY unless every
pre-registered gate has independently verifiable evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable

LIBRARIAN_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = LIBRARIAN_ROOT / "experiments" / "registry.json"
LIBRARIAN_LINK_PATH = LIBRARIAN_ROOT / "EXPERIMENT_REGISTRY_LINK.json"
RESEARCH_ASSISTANT_LINK_PATH = (
    LIBRARIAN_ROOT / "research_assistant" / "EXPERIMENT_REGISTRY_LINK.json"
)

REQUIRED_EXPERIMENT_FIELDS = {
    "experiment_id",
    "subsystem_layer",
    "claim_under_test",
    "falsifiable_hypothesis",
    "predicted_result",
    "null_alternative_outcome",
    "independent_variables",
    "dependent_variables",
    "controls",
    "dataset_source_requirements",
    "provenance_requirements",
    "pre_registered_protocol",
    "acceptance_rejection_thresholds",
    "statistical_reproducibility_criteria",
    "contamination_leakage_checks",
    "execution_prerequisites_stability_gates",
    "evidence_artifacts",
    "replication_plan",
    "external_literature_cross_check_status",
    "contradictory_findings",
    "result_status",
    "final_verdict",
}


class RegistryValidationError(RuntimeError):
    """The canonical registry or one of its reference views is invalid."""


class ExperimentExecutionDenied(RuntimeError):
    """Execution was requested without complete, verified readiness evidence."""


@dataclass(frozen=True)
class ReadinessDecision:
    experiment_id: str
    authorised: bool
    reasons: tuple[str, ...]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryValidationError(f"cannot read valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise RegistryValidationError(f"expected a JSON object: {path}")
    return value


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_nonempty_strings(values: Any, *, field: str, experiment_id: str) -> None:
    if not isinstance(values, list) or not values or not all(
        isinstance(value, str) and value.strip() for value in values
    ):
        raise RegistryValidationError(
            f"{experiment_id}.{field} must be a non-empty list of non-empty strings"
        )


def load_and_validate_registry(
    registry_path: Path | str = REGISTRY_PATH,
    *,
    verify_source_basis: bool = True,
) -> dict[str, Any]:
    """Load and structurally validate the canonical registry.

    Source-basis files are content-hash verified by default.  Missing or
    changed evidence invalidates the registry rather than degrading silently.
    """
    path = Path(registry_path)
    registry = _load_json(path)
    if registry.get("canonical") is not True:
        raise RegistryValidationError("registry is not marked canonical")
    if Path(registry.get("canonical_path", "")) != path:
        raise RegistryValidationError("canonical_path does not match the loaded registry")
    governance = registry.get("governance")
    if not isinstance(governance, dict) or governance.get("execution_default") != "DENY":
        raise RegistryValidationError("execution_default must be DENY")
    if governance.get("experiments_started") is not False:
        raise RegistryValidationError("registry does not certify experiments_started=false")

    gates = registry.get("global_stability_gates")
    if not isinstance(gates, list) or not gates or not all(isinstance(g, str) and g for g in gates):
        raise RegistryValidationError("global_stability_gates are missing or invalid")

    experiments = registry.get("experiments")
    if not isinstance(experiments, list) or not experiments:
        raise RegistryValidationError("experiments are missing")
    seen: set[str] = set()
    for experiment in experiments:
        if not isinstance(experiment, dict):
            raise RegistryValidationError("each experiment must be an object")
        missing = REQUIRED_EXPERIMENT_FIELDS - experiment.keys()
        experiment_id = str(experiment.get("experiment_id", "<missing-id>"))
        if missing:
            raise RegistryValidationError(f"{experiment_id} missing fields: {sorted(missing)}")
        if experiment_id in seen:
            raise RegistryValidationError(f"duplicate experiment_id: {experiment_id}")
        seen.add(experiment_id)
        for field in (
            "independent_variables",
            "dependent_variables",
            "controls",
            "dataset_source_requirements",
            "provenance_requirements",
            "pre_registered_protocol",
            "contamination_leakage_checks",
            "execution_prerequisites_stability_gates",
            "evidence_artifacts",
        ):
            _require_nonempty_strings(experiment[field], field=field, experiment_id=experiment_id)

    source_basis = registry.get("source_basis")
    if not isinstance(source_basis, list) or not source_basis:
        raise RegistryValidationError("source_basis is missing")
    if verify_source_basis:
        for source in source_basis:
            try:
                source_path = Path(source["path"])
                expected_hash = source["sha256"]
            except (KeyError, TypeError) as exc:
                raise RegistryValidationError("invalid source_basis entry") from exc
            if not source_path.is_file():
                raise RegistryValidationError(f"source-basis file missing: {source_path}")
            if _file_sha256(source_path) != expected_hash:
                raise RegistryValidationError(f"source-basis hash mismatch: {source_path}")
    return registry


def validate_reference_views(
    registry: dict[str, Any],
    link_paths: Iterable[Path | str] = (LIBRARIAN_LINK_PATH, RESEARCH_ASSISTANT_LINK_PATH),
) -> None:
    """Ensure both views contain only the same canonical IDs and path."""
    canonical_ids = [item["experiment_id"] for item in registry["experiments"]]
    for raw_path in link_paths:
        path = Path(raw_path)
        link = _load_json(path)
        if link.get("registry_id") != registry.get("registry_id"):
            raise RegistryValidationError(f"registry_id mismatch in {path}")
        if link.get("canonical_path") != registry.get("canonical_path"):
            raise RegistryValidationError(f"canonical_path mismatch in {path}")
        if link.get("experiment_ids") != canonical_ids:
            raise RegistryValidationError(f"experiment IDs diverged in {path}")
        if link.get("duplication_policy") != "REFERENCE_ONLY_DO_NOT_COPY_RECORDS":
            raise RegistryValidationError(f"unsafe duplication policy in {path}")


def _verified_gate(path: Path, expected_gate: str) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"missing gate evidence: {path.name}"
    try:
        record = _load_json(path)
    except RegistryValidationError as exc:
        return False, str(exc)
    if record.get("gate") != expected_gate or record.get("status") != "PASS":
        return False, f"gate is not a verified PASS: {expected_gate}"
    if not record.get("reviewer") or not record.get("verified_at"):
        return False, f"gate lacks reviewer or verification time: {expected_gate}"
    evidence_refs = record.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        return False, f"gate lacks evidence references: {expected_gate}"
    for ref in evidence_refs:
        if not isinstance(ref, dict) or not ref.get("path") or not ref.get("sha256"):
            return False, f"gate has malformed evidence reference: {expected_gate}"
        evidence_path = Path(ref["path"])
        if not evidence_path.is_file() or _file_sha256(evidence_path) != ref["sha256"]:
            return False, f"gate evidence missing or hash-mismatched: {expected_gate}"
    return True, ""


def assess_experiment_readiness(
    experiment_id: str,
    *,
    gate_evidence_dir: Path | str,
    registry_path: Path | str = REGISTRY_PATH,
    link_paths: Iterable[Path | str] = (LIBRARIAN_LINK_PATH, RESEARCH_ASSISTANT_LINK_PATH),
) -> ReadinessDecision:
    """Return DENY unless registry state and every gate artifact permit a run."""
    registry = load_and_validate_registry(registry_path)
    validate_reference_views(registry, link_paths)
    experiment = next(
        (item for item in registry["experiments"] if item["experiment_id"] == experiment_id),
        None,
    )
    if experiment is None:
        return ReadinessDecision(experiment_id, False, ("unknown experiment_id",))

    reasons: list[str] = []
    if experiment["result_status"] != "READY":
        reasons.append(f"result_status is {experiment['result_status']}, not READY")
    if experiment["final_verdict"] != "PENDING":
        reasons.append("final_verdict must be PENDING before execution")

    evidence_dir = Path(gate_evidence_dir)
    gate_sets = (
        ("global", registry["global_stability_gates"]),
        (experiment_id, experiment["execution_prerequisites_stability_gates"]),
    )
    for prefix, required_gates in gate_sets:
        for index, gate in enumerate(required_gates, start=1):
            valid, reason = _verified_gate(evidence_dir / f"{prefix}-{index:02d}.json", gate)
            if not valid:
                reasons.append(reason)
    return ReadinessDecision(experiment_id, not reasons, tuple(reasons))


def require_experiment_authorisation(
    experiment_id: str,
    *,
    gate_evidence_dir: Path | str,
    registry_path: Path | str = REGISTRY_PATH,
    link_paths: Iterable[Path | str] = (LIBRARIAN_LINK_PATH, RESEARCH_ASSISTANT_LINK_PATH),
) -> None:
    """Raise unless the experiment is explicitly READY and every gate verifies."""
    decision = assess_experiment_readiness(
        experiment_id,
        gate_evidence_dir=gate_evidence_dir,
        registry_path=registry_path,
        link_paths=link_paths,
    )
    if not decision.authorised:
        raise ExperimentExecutionDenied(
            f"execution denied for {experiment_id}: " + "; ".join(decision.reasons)
        )
