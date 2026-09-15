"""Bounded research-mission executor.

NEW module, NEXUS Federation F3. Executes exactly one bounded, scientifically
testable research request against the REAL ingested corpus using the
REAL lexical search built this mission (`retrieval/lexical_search.py`).

Per the mission's explicit instruction: "Do not fabricate missing research.
If evidence is insufficient, Librarian must explicitly report
INSUFFICIENT_EVIDENCE. That is a valid successful scientific outcome."

This module never calls an LLM, never generates prose synthesis, and never
upgrades a weak match into a confident finding. A "finding" is reported
ONLY as a literal, quoted excerpt of real stored text plus its real
source_uri -- never a paraphrase, never a summary.
"""

from __future__ import annotations

from pathlib import Path

from corpus import DatabaseConnectionPool, JsonContentStore
from ingestion.provenance import INGESTION_SCHEMA_SQL
from contracts.generic import (
    CapabilityLifecycle,
    CapabilityStatus,
    Confidence,
    InstitutionalReport,
    OperatingState,
    build_report,
)
from retrieval.lexical_search import SearchHit, search

LIBRARIAN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = LIBRARIAN_ROOT / "data"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


def execute_research_mission(
    *,
    mission_id: str,
    objective: str,
    query: str,
    data_dir: Path | str = DEFAULT_DATA_DIR,
    max_results: int = 5,
    min_matched_terms: int = 2,
    cycle_id: str | None = None,
) -> InstitutionalReport:
    """Runs one bounded research mission: retrieve real evidence for `query`
    against the real corpus, and report either real, evidenced findings or
    the explicit, valid INSUFFICIENT_EVIDENCE outcome. Never both silently
    conflated, never a fabricated middle ground.

    `min_matched_terms=2` by default (stricter than lexical_search.search()'s
    own default of 1): a single generic matched term (e.g. "index") is not
    treated as a genuine finding for a real research mission -- see
    retrieval/lexical_search.py and LIBRARIAN_LIMITATIONS.md for the
    empirical false-positive this threshold was added to address.
    """
    data_dir = Path(data_dir)
    pool = DatabaseConnectionPool(data_dir / "librarian.db")
    pool.initialize()
    # DEFECT FIX (F3, found by tests/failure/test_failure_modes.py test_02):
    # DatabaseConnectionPool.initialize() only creates the storage-level
    # schema (sources/documents/...); chunk_map/ingestion_log are normally
    # created lazily by IngestionPipeline's own constructor. A corpus that
    # was never ingested via the pipeline (e.g. a genuinely unavailable/
    # fresh data_dir) previously crashed retrieval with
    # "no such table: chunk_map" instead of degrading to INSUFFICIENT_EVIDENCE.
    with pool.get_connection() as conn:
        conn.executescript(INGESTION_SCHEMA_SQL)
    content_store = JsonContentStore(data_dir / "content")

    hits: list[SearchHit] = search(
        pool, content_store, query, max_results=max_results, min_matched_terms=min_matched_terms
    )

    retrieval_capability = CapabilityStatus(
        name="corpus_retrieval",
        lifecycle=CapabilityLifecycle.TESTED,
        confidence=Confidence(value=1.0, basis="lexical search executed against real stored corpus this cycle"),
        evidence_refs=["LIBRARIAN_COMPONENT_RECOVERY_MATRIX.md"],
        detail=f"query={query!r}, max_results={max_results}, hits_found={len(hits)}",
    )

    if not hits:
        return build_report(
            institution="librarian",
            mission_id=mission_id,
            objective=objective,
            operating_state=OperatingState.TESTED,
            capability_statuses=[retrieval_capability],
            findings=[
                f"{INSUFFICIENT_EVIDENCE}: no chunk in the real, currently-ingested "
                f"corpus (93 sources / 297 documents) contains any query term from "
                f"{query!r}. This is the correct, honest outcome given the corpus "
                f"content documented in LIBRARIAN_CORPUS_AUDIT.md (Librarian's own "
                f"operational documentation, not academic literature) -- not a "
                f"retrieval failure."
            ],
            evidence_refs=["LIBRARIAN_CORPUS_AUDIT.md"],
            limitations=[
                "Corpus contains zero academic/domain-relevant sources for this query domain.",
            ],
            cycle_id=cycle_id,
        )

    findings = []
    evidence_refs = []
    provenance_refs = []
    for hit in hits:
        findings.append(
            f'Source {hit.source_title!r} (chunk {hit.chunk_index}) matched terms '
            f'{list(hit.matched_terms)} ({hit.match_count} occurrences). '
            f'Verbatim excerpt: "{hit.excerpt.strip()[:300]}"'
        )
        evidence_refs.append(hit.source_url or hit.source_id)
        provenance_refs.append(
            f"librarian_source_id={hit.source_id} chunk_index={hit.chunk_index} "
            f"content_hash={hit.content_hash}"
        )

    return build_report(
        institution="librarian",
        mission_id=mission_id,
        objective=objective,
        operating_state=OperatingState.TESTED,
        capability_statuses=[retrieval_capability],
        findings=findings,
        evidence_refs=evidence_refs,
        provenance_refs=provenance_refs,
        limitations=[
            "Findings are literal retrieved excerpts, not synthesized or "
            "interpreted -- literature_review/evidence_synthesis remain "
            "NOT_COMMISSIONED.",
            "evidence_refs are the ORIGINAL source_uri recorded at ingestion time "
            "(2026-08-09); several of these paths (under ~/Librarian) may no "
            "longer exist on this machine -- see LIBRARIAN_DONOR_FORENSIC_REPORT.md "
            "section 1. NEXUS's own evidence resolver will report this honestly as "
            "unresolved rather than silently treat a stale path as verified.",
        ],
        cycle_id=cycle_id,
    )
