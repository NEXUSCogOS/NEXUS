"""Academic store and real-source ingestion tests."""

from __future__ import annotations

import pytest

from academic.ingest_real_sources import ingest_all, load_manifest
from academic.store import AcademicStore


@pytest.fixture
def store(tmp_path):
    return AcademicStore(tmp_path / "academic_corpus.db")


def test_manifest_loads_and_has_at_least_20_real_papers():
    manifest = load_manifest()
    assert len(manifest) >= 20
    for record in manifest:
        assert record["id"]
        assert record["title"]
        assert record["authors"]
        assert record["summary"]


def test_real_ingestion_is_idempotent(store):
    r1 = ingest_all(store)
    r2 = ingest_all(store)
    assert r1["created"] == r1["total_in_manifest"]
    assert r2["created"] == 0
    assert r2["skipped_existing"] == r1["total_in_manifest"]


def test_every_ingested_source_has_a_real_stable_identifier(store):
    ingest_all(store)
    for row in store.all_sources():
        assert row["source_id"].startswith("arxiv:") or row["source_id"].startswith("doi:")
        assert row["external_identifiers"].get("arxiv")


def test_no_source_stored_with_empty_retrievable_text(store):
    ingest_all(store)
    for row in store.all_sources():
        assert row["retrievable_text"].strip()


def test_academic_corpus_is_separate_from_internal_corpus_by_construction(store, tmp_path):
    """The academic store is a DIFFERENT SQLite file/schema from
    corpus/database.py's internal store -- proven structurally: this
    store has no `documents`/`sources` (internal schema) tables at all."""
    ingest_all(store)
    with store.connection() as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "academic_sources" in tables
    assert "documents" not in tables  # the internal corpus's table name
    assert "sources" not in tables  # the internal corpus's table name (distinct from "academic_sources")


def test_retraction_status_change_is_recorded_as_event_not_silent_overwrite(store):
    ingest_all(store)
    one = store.all_sources()[0]
    sid = one["source_id"]
    events_before = store.get_events(sid)

    store.set_retraction_status(sid, "RETRACTED", detail="test retraction")
    events_after = store.get_events(sid)

    assert len(events_after) == len(events_before) + 1
    assert store.get_source(sid)["retraction_status"] == "RETRACTED"
    # the INGESTED event is still present, never deleted
    assert any(e["event_type"] == "INGESTED" for e in events_after)
