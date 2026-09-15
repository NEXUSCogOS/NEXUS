"""Provenance graph construction and backward tracing.

New module, NEXUS Federation F2. Builds the chain:

    source document/data
        -> DAT.AI ingestion
        -> canonical spatial entity
        -> DAT.AI finding
        -> InstitutionalReport
        -> NEXUS executive state
        -> DelegationProposal

and answers "why does this executive state exist?" by walking
`parent_provenance_ids` backward to the source record(s).

This module is deliberately storage-agnostic: it takes a `lookup`
callable (`str -> Optional[ProvenanceRecord]`) rather than importing
persistence/db.py directly, so it can be exercised in tests against a
plain dict and, in the kernel, against the real FederationStore.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from provenance.model import ProvenanceRecord

if TYPE_CHECKING:
    from persistence.db import FederationStore

Lookup = Callable[[str], Optional[ProvenanceRecord]]


def make_store_lookup(store: "FederationStore") -> Lookup:
    """Adapt a FederationStore into a Lookup callable for trace_back()/
    explain() -- keeps this module free of a hard import-time dependency
    on persistence/db.py while still being trivially usable against the
    real store."""

    def _lookup(provenance_id: str) -> Optional[ProvenanceRecord]:
        raw = store.get_provenance_record(provenance_id)
        return ProvenanceRecord.model_validate(raw) if raw else None

    return _lookup


def trace_back(provenance_id: str, lookup: Lookup, *, _seen: Optional[set[str]] = None) -> list[ProvenanceRecord]:
    """Return the full chain of ancestor records reachable from
    `provenance_id`, in root-first order (the ultimate source first, the
    record itself last). Cycle-safe: a provenance_id already visited on
    this walk is not revisited (a provenance graph must be a DAG; a cycle
    here would indicate a bug upstream, not a valid state to loop on
    forever).
    """
    seen = _seen if _seen is not None else set()
    record = lookup(provenance_id)
    if record is None or provenance_id in seen:
        return []
    seen.add(provenance_id)

    chain: list[ProvenanceRecord] = []
    for parent_id in record.parent_provenance_ids:
        chain.extend(trace_back(parent_id, lookup, _seen=seen))
    chain.append(record)
    return chain


def explain(provenance_id: str, lookup: Lookup) -> str:
    """Human-readable "why does this exist" explanation: the chain from
    ultimate source to the given record, one line per hop."""
    chain = trace_back(provenance_id, lookup)
    if not chain:
        return f"no provenance record found for {provenance_id!r}"
    lines = []
    for i, record in enumerate(chain):
        prefix = "SOURCE" if i == 0 else f"  -> hop {i}"
        lines.append(
            f"{prefix}: [{record.source_type}] produced by {record.producer!r} "
            f"via {record.method!r} (verification={record.verification_status.value})"
        )
    return "\n".join(lines)


def root_verification_status(provenance_id: str, lookup: Lookup) -> Optional[str]:
    """The verification_status of the ULTIMATE source in the chain -- what
    NEXUS should report when asked "how well-founded is the root evidence
    behind this", as distinct from the verification_status of the record
    closest to the executive state itself, which may be VERIFIED even if
    its own source further back was only PARTIAL."""
    chain = trace_back(provenance_id, lookup)
    if not chain:
        return None
    return chain[0].verification_status.value
