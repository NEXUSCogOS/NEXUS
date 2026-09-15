"""Lexical retrieval over the ACADEMIC corpus — kept structurally
separate from `retrieval/lexical_search.py` (the internal NEXUS
documentation corpus), per the mission's explicit requirement that the
two corpora and their retrieval paths not be conflated (section 23).

NEW module, NEXUS Librarian F4. Same honest scope as the internal
lexical search: case-insensitive substring matching only, no semantic
ranking, no embeddings -- the current lexical baseline is a valid
baseline per the mission, not something to silently replace with an
unproven "improvement."
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from academic.store import AcademicStore

_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokenize(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text)]


@dataclass(frozen=True)
class AcademicSearchHit:
    source_id: str
    title: str
    source_type: str
    doi: str
    canonical_url: str
    retraction_status: str
    matched_terms: tuple[str, ...]
    match_count: int
    excerpt: str


def search(
    store: AcademicStore,
    query: str,
    *,
    max_results: int = 10,
    min_matched_terms: int = 2,
    exclude_retracted: bool = True,
) -> list[AcademicSearchHit]:
    """Deterministic lexical search over `retrievable_text` (the real
    abstract, for every source ingested this mission). A RETRACTED source
    is excluded by default (`exclude_retracted=True`) -- it must not
    silently remain ordinary evidence, per the mission's explicit
    instruction (section 9). Pass `exclude_retracted=False` only for
    provenance/audit purposes, never for a real research finding.
    """
    terms = sorted(set(_tokenize(query)))
    if not terms:
        return []

    candidate_ids = store.fts_candidate_ids(terms)
    rows = store.all_sources() if candidate_ids is None else store.get_sources_by_ids(candidate_ids)
    hits: list[AcademicSearchHit] = []
    for row in rows:
        if exclude_retracted and row["retraction_status"] == "RETRACTED":
            continue
        text = row["retrievable_text"] or ""
        lowered = text.lower()
        matched = tuple(t for t in terms if t in lowered)
        if len(matched) < min_matched_terms:
            continue
        match_count = sum(lowered.count(t) for t in matched)
        hits.append(
            AcademicSearchHit(
                source_id=row["source_id"],
                title=row["title"],
                source_type=row["source_type"],
                doi=row["doi"],
                canonical_url=row["canonical_url"],
                retraction_status=row["retraction_status"],
                matched_terms=matched,
                match_count=match_count,
                excerpt=text[:500],
            )
        )

    hits.sort(key=lambda h: (-h.match_count, h.source_id))
    return hits[:max_results]
