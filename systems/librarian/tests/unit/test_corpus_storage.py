import pytest

from corpus import (
    Source,
    Document,
    QueryHistory,
    DatabaseConnectionPool,
    SourceStore,
    DocumentStore,
    QueryHistoryStore,
    JsonContentStore,
    content_hash,
)


@pytest.fixture
def pool(tmp_path):
    p = DatabaseConnectionPool(tmp_path / "librarian.db")
    p.initialize()
    return p


def test_source_round_trip(pool):
    store = SourceStore(pool)
    src = Source(
        source_id="s1",
        title="Attention Is All You Need",
        source_type="paper",
        url="https://example.org/attention",
        tags=["transformers", "nlp"],
        metadata={"venue": "NeurIPS"},
    )
    assert store.create(src)

    got = store.get("s1")
    assert got is not None
    assert got.title == src.title
    assert got.tags == ["transformers", "nlp"]
    assert got.metadata["venue"] == "NeurIPS"
    assert store.count_active() == 1


def test_source_url_uniqueness(pool):
    store = SourceStore(pool)
    a = Source(source_id="a", title="A", source_type="paper", url="https://dup")
    b = Source(source_id="b", title="B", source_type="paper", url="https://dup")
    assert store.create(a)
    assert store.create(b) is False


def test_source_soft_delete_excludes_from_listing(pool):
    store = SourceStore(pool)
    store.create(Source(source_id="s1", title="T", source_type="paper"))
    assert store.delete("s1")
    assert store.count_active() == 0
    assert store.list_active() == []
    assert store.get("s1") is not None


def test_document_dedup_by_content_hash(pool):
    SourceStore(pool).create(Source(source_id="s1", title="T", source_type="paper"))
    docs = DocumentStore(pool)
    h = content_hash("shared body text")

    assert docs.create(Document("d1", "s1", "chunk 0", h, 0, 12))
    assert docs.create(Document("d2", "s1", "chunk 1", h, 1, 12)) is False

    assert docs.get_by_hash(h).document_id == "d1"
    assert docs.count_by_source("s1") == 1


def test_documents_listed_in_chunk_order(pool):
    SourceStore(pool).create(Source(source_id="s1", title="T", source_type="paper"))
    docs = DocumentStore(pool)
    for i in (2, 0, 1):
        docs.create(Document(f"d{i}", "s1", f"c{i}", content_hash(f"body {i}"), i, 5))

    assert [d.chunk_index for d in docs.list_by_source("s1")] == [0, 1, 2]


def test_query_history_logs_and_accepts_feedback(pool):
    store = QueryHistoryStore(pool)
    q = QueryHistory(
        query_id="q1",
        query_text="what is attention",
        query_type="hybrid",
        result_count=3,
        result_metadata={"top_score": 0.91},
    )
    assert store.log_query(q)

    got = store.get_query("q1")
    assert got.result_metadata["top_score"] == 0.91
    assert len(store.list_recent(query_type="hybrid")) == 1
    assert len(store.list_recent(query_type="semantic")) == 0

    assert store.set_feedback("q1", "helpful")
    assert store.get_query("q1").user_feedback == "helpful"


def test_json_content_store_round_trip(tmp_path):
    cs = JsonContentStore(tmp_path / "content")
    h = cs.put("s1", "d1", "  body text  ")

    assert h == content_hash("body text")
    assert cs.get("s1", "d1") == "  body text  "

    cs.put("s1", "d2", "second")
    assert set(cs.get_all("s1")) == {"d1", "d2"}

    assert cs.delete("s1", "d1")
    assert cs.get("s1", "d1") is None
    assert cs.delete("s1", "d1") is False

    assert cs.delete_source("s1")
    assert cs.get_all("s1") == {}
