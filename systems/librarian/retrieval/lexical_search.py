"""Minimal lexical (substring/keyword) search over the ingested corpus.

NEW module, NEXUS Federation F3. No retrieval/search capability exists
anywhere in the Librarian donor (confirmed in
LIBRARIAN_DONOR_FORENSIC_REPORT.md and LIBRARIAN_COMPONENT_RECOVERY_MATRIX.md
— classification NOT_FOUND, decision REENGINEER). This is deliberately the
SMALLEST honest capability that lets Librarian answer a real research
request with real evidence rather than fabricated synthesis: case-insensitive
substring matching of query terms against each chunk's actual stored text,
scored only by how many distinct query terms matched and how often --
no embeddings, no semantic ranking, no LLM call, nothing that could produce
a plausible-looking result unsupported by the literal text.

This does NOT claim to be literature review, evidence synthesis, or any of
the NOT_COMMISSIONED capabilities in `institutional/reporter.py` — it is
retrieval only. Returning zero matches for a real research question is a
valid, expected outcome given the corpus content documented in
LIBRARIAN_CORPUS_AUDIT.md (the ingested corpus is Librarian's own
operational documentation, not academic literature) -- see
`runtime/research_executor.py` for how a zero-match result becomes an
honest INSUFFICIENT_EVIDENCE report rather than a fabricated finding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from corpus import DatabaseConnectionPool, JsonContentStore
from ingestion.pipeline import CONTENT_BUCKET

_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokenize(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text)]


@dataclass(frozen=True)
class SearchHit:
    source_id: str
    source_title: str
    source_url: str | None
    chunk_index: int
    content_hash: str
    matched_terms: tuple[str, ...]
    match_count: int
    excerpt: str


def search(
    pool: DatabaseConnectionPool,
    content_store: JsonContentStore,
    query: str,
    *,
    max_results: int = 10,
    min_matched_terms: int = 1,
) -> list[SearchHit]:
    """Case-insensitive substring match of every distinct query term
    against every chunk's real stored text. Deterministic: identical
    corpus + identical query always yields identical results and ordering
    (sorted by match_count desc, then source_id/chunk_index for a total
    order — never a random/unstable ranking).

    `min_matched_terms` (default 1): empirically, a single generic query
    term (e.g. "index") can match a chunk for reasons unrelated to the
    query's real intent (e.g. a CSV/database "index" command, not a
    "spatial index" in the geospatial sense) -- see LIBRARIAN_LIMITATIONS.md.
    Callers building a real research-mission report (runtime/
    research_executor.py) pass a higher threshold so an isolated common-word
    coincidence is not reported as a genuine finding.
    """
    terms = sorted(set(_tokenize(query)))
    if not terms:
        return []

    hits: list[SearchHit] = []
    with pool.get_connection() as conn:
        sources = {
            row["source_id"]: (row["title"], row["url"])
            for row in conn.execute(
                "SELECT source_id, title, url FROM sources WHERE is_active = 1"
            ).fetchall()
        }
        chunk_rows = conn.execute(
            "SELECT source_id, chunk_index, content_hash FROM chunk_map "
            "ORDER BY source_id, chunk_index"
        ).fetchall()

    for row in chunk_rows:
        source_id = row["source_id"]
        if source_id not in sources:
            continue  # soft-deleted source; do not surface as evidence
        text = content_store.get(CONTENT_BUCKET, row["content_hash"])
        if not text:
            continue
        lowered = text.lower()
        matched = tuple(t for t in terms if t in lowered)
        if len(matched) < min_matched_terms:
            continue
        match_count = sum(lowered.count(t) for t in matched)
        title, url = sources[source_id]
        hits.append(
            SearchHit(
                source_id=source_id,
                source_title=title,
                source_url=url,
                chunk_index=row["chunk_index"],
                content_hash=row["content_hash"],
                matched_terms=matched,
                match_count=match_count,
                excerpt=text[:400],
            )
        )

    hits.sort(key=lambda h: (-h.match_count, h.source_id, h.chunk_index))
    return hits[:max_results]
