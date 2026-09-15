"""Librarian's InstitutionalReport adapter.

NEW module, NEXUS Federation F3. Lives in `reporting/` rather than the
mission target tree's literal `institutional/` name because a top-level
`institutional` package here would collide with DAT.AI's own
`institutional` package once both institutions' code is importable in the
same federation test/kernel process (Python caches modules by top-level
name in `sys.modules` -- a second same-named package is not merged, it
either errors or silently resolves to whichever was imported first). See
LIBRARIAN_CANONICAL_ARCHITECTURE.md.

Builds Librarian's `InstitutionalReport` using NEXUS Federation's GENERIC
contract (`nexus_federation.contracts.generic`) — per the mission's
explicit instruction, this is NOT a Librarian-specific federation parser;
Librarian populates the same shared schema DAT.AI's contract independently
also satisfies conceptually, with its own institution id and its own real
capability evidence.

Every capability status below is backed by a real, this-mission-verified
check (test counts, database row counts, or an explicit absence) — never
inferred from a filename or a donor claim. See
LIBRARIAN_COMPONENT_RECOVERY_MATRIX.json for the evidence behind each one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from contracts.generic import (
    CapabilityLifecycle,
    CapabilityStatus,
    Confidence,
    InstitutionalReport,
    OperatingState,
    ResourceUsage,
    StorageState,
    build_report,
)

LIBRARIAN_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = LIBRARIAN_ROOT / "data"


def _corpus_ingestion_capability() -> CapabilityStatus:
    """Real, tested corpus ingestion pipeline (source discovery,
    provenance, dedup, chunking) -- see LIBRARIAN_CANONICAL_TEST_BASELINE.md."""
    return CapabilityStatus(
        name="corpus_ingestion",
        lifecycle=CapabilityLifecycle.INTEGRATED,
        confidence=Confidence(value=1.0, basis="22/22 recovered unit tests pass; real DB 93 sources/297 documents/371 chunks re-verified"),
        evidence_refs=["LIBRARIAN_CANONICAL_TEST_BASELINE.md", "LIBRARIAN_DONOR_FORENSIC_REPORT.md"],
        detail="Staged discovery->normalize->chunk->dedup->persist pipeline, recovered from librarian_rag donor unchanged.",
    )


def _corpus_storage_capability() -> CapabilityStatus:
    db_exists = DATA_DIR.joinpath("librarian.db").exists()
    if not db_exists:
        return CapabilityStatus(
            name="corpus_storage",
            lifecycle=CapabilityLifecycle.DEGRADED,
            confidence=Confidence.unknown(),
            evidence_refs=["LIBRARIAN_DONOR_FORENSIC_REPORT.md"],
            detail="librarian.db not found at expected path -- corpus storage degraded, not fabricated as healthy.",
        )
    return CapabilityStatus(
        name="corpus_storage",
        lifecycle=CapabilityLifecycle.INTEGRATED,
        confidence=Confidence(value=1.0, basis="SQLite + JSON content store real and present; 7/7 recovered storage tests pass"),
        evidence_refs=["LIBRARIAN_CANONICAL_TEST_BASELINE.md"],
        detail="Real database present at data/librarian.db (byte-identical copy of donor's ingested corpus).",
    )


def _corpus_retrieval_capability() -> CapabilityStatus:
    """New this mission -- minimal lexical search. Honestly IMPLEMENTED +
    TESTED, never claimed as semantic/embedding-based (that capability
    does not exist)."""
    return CapabilityStatus(
        name="corpus_retrieval",
        lifecycle=CapabilityLifecycle.TESTED,
        confidence=Confidence(value=1.0, basis="new lexical search built and tested this mission; see tests/unit/test_lexical_search.py"),
        evidence_refs=["LIBRARIAN_COMPONENT_RECOVERY_MATRIX.md"],
        detail="Lexical (substring) search only -- no semantic/embedding retrieval exists.",
    )


def _literature_review_capability() -> CapabilityStatus:
    return CapabilityStatus(
        name="literature_review",
        lifecycle=CapabilityLifecycle.NOT_COMMISSIONED,
        confidence=Confidence.unknown(),
        evidence_refs=["LIBRARIAN_COMPONENT_RECOVERY_MATRIX.md"],
        detail="No literature-review/synthesis code exists in the donor; not fabricated this mission.",
    )


def _citation_provenance_capability() -> CapabilityStatus:
    return CapabilityStatus(
        name="citation_academic_metadata",
        lifecycle=CapabilityLifecycle.NOT_COMMISSIONED,
        confidence=Confidence.unknown(),
        evidence_refs=["LIBRARIAN_CORPUS_AUDIT.md"],
        detail="No author/DOI/journal metadata is ever populated; source-level provenance (hash/version) IS real -- see corpus_ingestion.",
    )


def _hypothesis_project_paper_capability() -> CapabilityStatus:
    return CapabilityStatus(
        name="hypothesis_project_paper_generation",
        lifecycle=CapabilityLifecycle.NOT_COMMISSIONED,
        confidence=Confidence.unknown(),
        evidence_refs=["LIBRARIAN_COMPONENT_RECOVERY_MATRIX.md"],
        detail="Donor only had an unfilled-template generator script (ARCHIVEd); no automation exists.",
    )


def all_capability_statuses() -> list[CapabilityStatus]:
    return [
        _corpus_ingestion_capability(),
        _corpus_storage_capability(),
        _corpus_retrieval_capability(),
        _literature_review_capability(),
        _citation_provenance_capability(),
        _hypothesis_project_paper_capability(),
    ]


def _derive_operating_state(capabilities: list[CapabilityStatus]) -> OperatingState:
    core = next((c for c in capabilities if c.name == "corpus_retrieval"), None)
    if core is None:
        return OperatingState.UNAVAILABLE
    mapping = {
        CapabilityLifecycle.NOT_IMPLEMENTED: OperatingState.UNAVAILABLE,
        CapabilityLifecycle.IMPLEMENTED: OperatingState.IMPLEMENTED,
        CapabilityLifecycle.TESTED: OperatingState.TESTED,
        CapabilityLifecycle.INTEGRATED: OperatingState.INTEGRATED,
        CapabilityLifecycle.EMPIRICALLY_VALIDATED: OperatingState.EMPIRICALLY_VALIDATED,
        CapabilityLifecycle.OPERATIONAL: OperatingState.OPERATIONAL,
    }
    return mapping.get(core.lifecycle, OperatingState.DEGRADED)


def build_current_report(
    *,
    mission_id: str,
    objective: str = "Librarian institutional self-report",
    findings: Optional[list[str]] = None,
    evidence_refs: Optional[list[str]] = None,
    cycle_id: Optional[str] = None,
) -> InstitutionalReport:
    caps = all_capability_statuses()
    return build_report(
        institution="librarian",
        mission_id=mission_id,
        objective=objective,
        operating_state=_derive_operating_state(caps),
        capability_statuses=caps,
        findings=findings or [],
        evidence_refs=evidence_refs or ["LIBRARIAN_CANONICAL_TEST_BASELINE.md"],
        limitations=[
            "No literature review, citation metadata, hypothesis, project, or paper "
            "generation capability exists -- honestly reported NOT_COMMISSIONED.",
            "Ingested corpus is Librarian's own operational documentation, not academic "
            "literature -- see LIBRARIAN_CORPUS_AUDIT.md.",
        ],
        cycle_id=cycle_id,
    )
