from __future__ import annotations

import hashlib
import json
from pathlib import Path

PROHIBITED_MARKERS = (
    "/publication/",
    "/archive/",
    "/legacy_",
    "/historical_",
    "/invalid_research_claims/",
    "/experiments/registry.json",
    "/EXPERIMENT_REGISTRY_LINK.json",
)

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def _resolve_evidence_path(raw: str, nexus_root: Path | None) -> Path:
    """Resolve portable evidence references against explicit NEXUS authority."""
    marker = "${NEXUS_ROOT}/"

    if raw.startswith(marker):
        if nexus_root is None:
            raise ValueError("NEXUS_ROOT_REQUIRED")

        root = Path(nexus_root).expanduser().resolve()
        relative = raw[len(marker):]

        candidate = (root / relative).resolve()

        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                "EVIDENCE_PATH_ESCAPES_NEXUS_ROOT"
            ) from exc

        return candidate

    return Path(raw)


def validate_gate_record(
    record_path: Path,
    canonical_gate: dict,
    nexus_root: Path | None = None,
) -> dict:
    reasons = []

    try:
        record = json.loads(record_path.read_text())
    except Exception as exc:
        return {"valid": False, "reasons": [f"INVALID_JSON:{exc}"]}

    if record.get("gate_id") != canonical_gate["gate_id"]:
        reasons.append("GATE_ID_MISMATCH")

    if record.get("gate") != canonical_gate["canonical_gate_text"]:
        reasons.append("EXACT_GATE_TEXT_MISMATCH")

    if record.get("status") != "PASS":
        reasons.append("STATUS_NOT_PASS")

    reviewer = record.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        reasons.append("REVIEWER_MISSING")

    verified_at = (
        record.get("verified_at")
        or record.get("verification_time")
        or record.get("verified_at_utc")
    )

    if not isinstance(verified_at, str) or not verified_at.strip():
        reasons.append("VERIFICATION_TIME_MISSING")

    if record.get("contradictions_resolved") is not True:
        reasons.append("CONTRADICTIONS_NOT_RESOLVED")

    refs = (
        record.get("evidence_refs")
        or record.get("evidence_references")
    )

    if not isinstance(refs, list) or not refs:
        reasons.append("EVIDENCE_REFS_MISSING")
        refs = []

    validated = []

    for ref in refs:
        if not isinstance(ref, dict):
            reasons.append("MALFORMED_EVIDENCE_REF")
            continue

        raw = ref.get("path")
        expected = ref.get("sha256")

        if not raw:
            reasons.append("EVIDENCE_PATH_MISSING")
            continue

        try:
            path = _resolve_evidence_path(
                raw,
                nexus_root,
            )
        except ValueError as exc:
            reasons.append(f"{exc}:{raw}")
            continue

        if not path.is_absolute():
            reasons.append(
                f"EVIDENCE_PATH_NOT_ABSOLUTE:{raw}"
            )
            continue

        if not path.is_file():
            reasons.append(f"EVIDENCE_FILE_MISSING:{path}")
            continue

        if any(x in str(path) for x in PROHIBITED_MARKERS):
            reasons.append(f"PROHIBITED_EVIDENCE_SOURCE:{path}")

        if not isinstance(expected, str) or len(expected) != 64:
            reasons.append(f"EVIDENCE_HASH_MISSING_OR_INVALID:{path}")
            continue

        actual = sha256(path)

        if actual != expected:
            reasons.append(f"EVIDENCE_HASH_MISMATCH:{path}")
            continue

        validated.append({
            "path": str(path),
            "sha256": actual,
        })

    return {
        "valid": not reasons,
        "gate_id": canonical_gate["gate_id"],
        "reasons": reasons,
        "validated_evidence_refs": validated,
    }
