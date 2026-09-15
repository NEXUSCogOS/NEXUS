"""Evidence resolution.

New module, NEXUS Federation F1. An evidence_ref string inside an
InstitutionalReport is a claim, not proof. This module is the only place
that claim is checked against reality: does the referenced artifact
actually exist, and (across successive resolutions) has its content
drifted since NEXUS first saw it.

Explicit limitation, stated rather than papered over: DAT.AI's contract
(institutional/contract.py) carries evidence_refs as plain strings with no
accompanying expected hash. This module therefore cannot verify a ref
against an *expected* hash on first resolution -- there is nothing to
compare against. What it CAN and does do: confirm the artifact exists,
record its hash as a baseline, and on every subsequent resolution of the
same (institution, ref) pair, detect drift against that baseline. This is
real integrity monitoring, honestly scoped to what the input data supports.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Named, explicit search roots -- not hidden magic. Each institution's
# evidence_refs are resolved against whichever of these roots contains a
# matching file, first match wins, and the resolution result records which
# root actually answered.
SEARCH_ROOTS: list[tuple[str, Path]] = [
    ("dat_ai_canonical", Path("${NEXUS_ROOT}/systems/dat_ai")),
    ("dat_ai_canonical_docs", Path("${NEXUS_ROOT}/systems/dat_ai/docs")),
    (
        "engineering_studio_audit_trail",
        Path("${HOME}/Desktop/Claude Audit/Audit "),
    ),
]

_COMMIT_HASH_RE = re.compile(r"\b[0-9a-f]{7,40}\b")

# Bumped whenever the resolution algorithm itself changes (search roots,
# hashing method, syntactic-validity rules) -- recorded on every ledger
# row (NEXUS Federation F2) so a historical resolution can be understood
# in light of the resolver version that produced it.
RESOLVER_VERSION = "1.0.0"


@dataclass(frozen=True)
class EvidenceResolution:
    ref: str
    syntactically_valid: bool
    resolved: bool
    resolved_path: Optional[str]
    resolved_root: Optional[str]
    sha256: Optional[str]
    reason: str


def _is_syntactically_valid(ref: str) -> bool:
    if not ref or not ref.strip():
        return False
    if "\x00" in ref:
        return False
    if len(ref) > 4096:
        return False
    return True


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_evidence_ref(
    ref: str, *, search_roots: list[tuple[str, Path]] | None = None
) -> EvidenceResolution:
    """Resolve one evidence_ref string against known search roots."""
    roots = search_roots if search_roots is not None else SEARCH_ROOTS

    if not _is_syntactically_valid(ref):
        return EvidenceResolution(
            ref=ref,
            syntactically_valid=False,
            resolved=False,
            resolved_path=None,
            resolved_root=None,
            sha256=None,
            reason="empty, null-byte-containing, or implausibly long ref",
        )

    for root_name, root_path in roots:
        candidate = root_path / ref
        try:
            if candidate.is_file():
                return EvidenceResolution(
                    ref=ref,
                    syntactically_valid=True,
                    resolved=True,
                    resolved_path=str(candidate),
                    resolved_root=root_name,
                    sha256=_hash_file(candidate),
                    reason=f"resolved under root {root_name!r}",
                )
        except OSError:
            continue

    return EvidenceResolution(
        ref=ref,
        syntactically_valid=True,
        resolved=False,
        resolved_path=None,
        resolved_root=None,
        sha256=None,
        reason=f"not found under any of {len(roots)} configured search roots",
    )


def resolve_all(refs: list[str]) -> list[EvidenceResolution]:
    return [resolve_evidence_ref(ref) for ref in refs]


def detect_drift(
    resolution: EvidenceResolution, previously_recorded_sha256: Optional[str]
) -> Optional[str]:
    """Compare a fresh resolution's hash against a previously-persisted
    baseline for the SAME (institution, ref) pair. Returns a human-readable
    drift description, or None if unchanged / nothing to compare (first
    time seeing this ref, or it isn't resolvable at all).
    """
    if not resolution.resolved or previously_recorded_sha256 is None:
        return None
    if resolution.sha256 != previously_recorded_sha256:
        return (
            f"evidence content changed since last resolution: "
            f"{previously_recorded_sha256[:12]} -> {resolution.sha256[:12]}"
        )
    return None


def looks_like_commit_reference(provenance_ref: str) -> Optional[str]:
    """Provenance refs are often prose with an embedded commit hash (e.g.
    'NEXUS_LOCAL donor commit eb9ed1c (systems/dat_ai)') rather than a clean
    identifier. Extract the hash-like substring if present; return None if
    the text carries no independently-checkable commit reference. This is
    an honest partial check: it identifies a candidate hash, it does not
    verify the hash exists in any particular repository (that would require
    knowing which repo to check per provenance_ref, not yet standardized).
    """
    match = _COMMIT_HASH_RE.search(provenance_ref)
    return match.group(0) if match else None
