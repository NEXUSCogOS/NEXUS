"""Append-only evidence relationships for canonical NEXUS experiments."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from runtime.experiment_registry import REGISTRY_PATH, load_and_validate_registry

ALLOWED_RELATIONSHIPS = {
    "CONFIRMS",
    "CONTRADICTS",
    "QUALIFIES",
    "DISPROVES",
    "INSUFFICIENT",
    "UNVERIFIABLE",
}
REQUIRED_FIELDS = {
    "experiment_id",
    "relationship",
    "source_identifier",
    "source_title",
    "source_path",
    "source_sha256",
    "citation",
    "passage_locator",
    "acquired_at",
    "verified_at",
    "reviewer",
    "method_context",
    "limitations",
    "confidence_basis",
}


class EvidenceRecordRejected(ValueError):
    """Evidence was not appended because provenance could not be verified."""


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_timestamp(value: str, field: str) -> None:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise EvidenceRecordRejected(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise EvidenceRecordRejected(f"{field} must include a timezone")


def _last_event_hash(ledger_path: Path) -> str | None:
    if not ledger_path.exists():
        return None
    last: dict[str, Any] | None = None
    for line_number, line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EvidenceRecordRejected(f"ledger corruption at line {line_number}") from exc
        expected = event.get("event_sha256")
        unsigned = {key: value for key, value in event.items() if key != "event_sha256"}
        if expected != sha256(_canonical_json(unsigned)).hexdigest():
            raise EvidenceRecordRejected(f"ledger hash mismatch at line {line_number}")
        if last is not None and event.get("previous_event_sha256") != last["event_sha256"]:
            raise EvidenceRecordRejected(f"ledger chain mismatch at line {line_number}")
        last = event
    return None if last is None else last["event_sha256"]


def append_evidence_relationship(
    record: dict[str, Any],
    *,
    ledger_path: Path | str,
    registry_path: Path | str = REGISTRY_PATH,
) -> dict[str, Any]:
    """Validate provenance and append one hash-chained relationship event.

    The source must exist locally and match its declared SHA-256.  Existing
    ledger events are verified before appending, so corruption fails closed.
    """
    missing = REQUIRED_FIELDS - record.keys()
    if missing:
        raise EvidenceRecordRejected(f"missing evidence fields: {sorted(missing)}")
    relationship = record["relationship"]
    if relationship not in ALLOWED_RELATIONSHIPS:
        raise EvidenceRecordRejected(f"unsupported relationship: {relationship}")
    for field in REQUIRED_FIELDS:
        if not isinstance(record[field], str) or not record[field].strip():
            raise EvidenceRecordRejected(f"{field} must be a non-empty string")
    _parse_timestamp(record["acquired_at"], "acquired_at")
    _parse_timestamp(record["verified_at"], "verified_at")

    registry = load_and_validate_registry(registry_path)
    canonical_ids = {item["experiment_id"] for item in registry["experiments"]}
    if record["experiment_id"] not in canonical_ids:
        raise EvidenceRecordRejected("experiment_id is not canonical")

    source_path = Path(record["source_path"])
    if not source_path.is_file():
        raise EvidenceRecordRejected("source_path does not resolve to a file")
    if _hash_file(source_path) != record["source_sha256"]:
        raise EvidenceRecordRejected("source SHA-256 does not match")

    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    previous_hash = _last_event_hash(path)
    event = dict(record)
    event["previous_event_sha256"] = previous_hash
    event["event_sha256"] = sha256(_canonical_json(event)).hexdigest()
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
        stream.flush()
    return event
