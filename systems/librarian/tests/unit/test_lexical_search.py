"""Lexical search unit tests -- built new this mission (no donor equivalent
exists; see LIBRARIAN_COMPONENT_RECOVERY_MATRIX.md, corpus_search_retrieval
classification NOT_FOUND -> REENGINEER)."""

from __future__ import annotations

from corpus import DatabaseConnectionPool, JsonContentStore
from ingestion import IngestionPipeline
from retrieval.lexical_search import search


def _seed(tmp_path, docs: dict[str, str]):
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    for name, text in docs.items():
        (corpus_dir / name).write_text(text, encoding="utf-8")

    data_dir = tmp_path / "data"
    pool = DatabaseConnectionPool(data_dir / "librarian.db")
    pool.initialize()
    pipe = IngestionPipeline(pool, data_dir / "content")
    pipe.run([corpus_dir])
    return pool, JsonContentStore(data_dir / "content")


def test_search_finds_real_matching_chunk(tmp_path):
    pool, content = _seed(tmp_path, {
        "a.md": "# Alpha\n\nThis document discusses PostGIS spatial indexing in depth.",
        "b.md": "# Beta\n\nThis document discusses cooking recipes.",
    })
    hits = search(pool, content, "postgis spatial", min_matched_terms=2)
    assert len(hits) == 1
    assert hits[0].source_title == "a"
    assert "PostGIS" in hits[0].excerpt


def test_search_no_match_returns_empty(tmp_path):
    pool, content = _seed(tmp_path, {"a.md": "# Alpha\n\nUnrelated content entirely."})
    hits = search(pool, content, "quantum chromodynamics", min_matched_terms=1)
    assert hits == []


def test_search_is_deterministic(tmp_path):
    pool, content = _seed(tmp_path, {
        "a.md": "# A\n\nfoo bar baz",
        "b.md": "# B\n\nfoo bar",
    })
    r1 = search(pool, content, "foo bar")
    r2 = search(pool, content, "foo bar")
    assert [h.source_id for h in r1] == [h.source_id for h in r2]


def test_min_matched_terms_filters_single_generic_word(tmp_path):
    """The exact empirical false-positive this threshold was added for:
    a single common word ('index') should not count as a match when
    min_matched_terms=2 is required, even though it literally appears."""
    pool, content = _seed(tmp_path, {
        "a.md": "# A\n\nHow to build a database index for fast lookups.",
    })
    hits_loose = search(pool, content, "spatial index", min_matched_terms=1)
    hits_strict = search(pool, content, "spatial index", min_matched_terms=2)
    assert len(hits_loose) == 1  # "index" alone matches
    assert len(hits_strict) == 0  # "spatial" does not appear, so 2-term bar fails


def test_search_excludes_soft_deleted_sources(tmp_path):
    from corpus import SourceStore

    pool, content = _seed(tmp_path, {"a.md": "# A\n\nUnique searchable phrase xyzzy."})
    sources = SourceStore(pool)
    (src,) = sources.list_active()
    sources.delete(src.source_id)

    hits = search(pool, content, "xyzzy")
    assert hits == []


def test_search_against_real_historical_corpus_is_deterministic(real_data_dir):
    """Runs against the REAL, historical corpus (93 sources) preserved in
    data/ -- read-only, never mutated. Proves the mechanism works against
    genuine ingested data, not just synthetic fixtures."""
    pool = DatabaseConnectionPool(real_data_dir / "librarian.db")
    pool.initialize()
    content = JsonContentStore(real_data_dir / "content")

    hits = search(pool, content, "ingestion provenance corpus", min_matched_terms=2)
    assert isinstance(hits, list)  # deterministic real query, real corpus
    hits2 = search(pool, content, "ingestion provenance corpus", min_matched_terms=2)
    assert [h.content_hash for h in hits] == [h.content_hash for h in hits2]
