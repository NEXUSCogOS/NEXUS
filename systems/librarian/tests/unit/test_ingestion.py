from pathlib import Path

import pytest

from corpus import DatabaseConnectionPool, SourceStore
from ingestion import normalize_text, chunk_text
from ingestion.pipeline import IngestionPipeline, _source_id, CONTENT_BUCKET


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #
@pytest.fixture
def env(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    data = tmp_path / "data"
    pool = DatabaseConnectionPool(data / "librarian.db")
    pool.initialize()
    pipe = IngestionPipeline(pool, data / "content")
    return {"corpus": corpus, "pool": pool, "pipe": pipe}


def write(corpus: Path, rel: str, text: str) -> Path:
    p = corpus / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _count(pool, table, where="", args=()):
    with pool.get_connection() as conn:
        return conn.execute(
            f"SELECT COUNT(*) c FROM {table} {where}", args
        ).fetchone()["c"]


# --------------------------------------------------------------------------- #
# Deterministic normalization / chunking                                      #
# --------------------------------------------------------------------------- #
def test_normalize_is_deterministic_and_idempotent():
    raw = "Title\r\n\r\n\r\n\r\nBody line   \r\n\r\n"
    once = normalize_text(raw)
    # CRLF->LF, trailing ws stripped, 4 blank lines collapsed to exactly 2.
    assert once == "Title\n\n\nBody line"
    assert normalize_text(once) == once  # idempotent


def test_chunk_ordering_is_sequential():
    text = "\n\n".join(f"Paragraph number {i} " + "x" * 400 for i in range(6))
    chunks = chunk_text(normalize_text(text))
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert len(chunks) > 1  # actually split


def test_oversized_paragraph_is_hard_split():
    big = "y" * 5000
    chunks = chunk_text(normalize_text(big))
    assert len(chunks) >= 3
    assert all(len(c.text) <= 2000 for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))


# --------------------------------------------------------------------------- #
# 1. Duplicate ingestion (idempotency)                                        #
# --------------------------------------------------------------------------- #
def test_duplicate_ingestion_is_idempotent(env):
    write(env["corpus"], "a.md", "# A\n\nAlpha body paragraph.")
    write(env["corpus"], "b.md", "# B\n\nBeta body paragraph.")

    r1 = env["pipe"].run([env["corpus"]])
    assert r1.created == 2

    s1 = _count(env["pool"], "sources")
    d1 = _count(env["pool"], "documents")
    m1 = _count(env["pool"], "chunk_map")

    r2 = env["pipe"].run([env["corpus"]])
    assert r2.created == 0
    assert r2.skipped_unchanged == 2

    assert _count(env["pool"], "sources") == s1
    assert _count(env["pool"], "documents") == d1
    assert _count(env["pool"], "chunk_map") == m1


# --------------------------------------------------------------------------- #
# 2. Changed source detection                                                 #
# --------------------------------------------------------------------------- #
def test_changed_source_is_reprocessed(env):
    p = write(env["corpus"], "a.md", "# A\n\nOriginal body.")
    env["pipe"].run([env["corpus"]])

    sid = _source_id(str(p.resolve()))
    before = SourceStore(env["pool"]).get(sid).metadata["source_hash"]

    p.write_text("# A\n\nCompletely different body now.", encoding="utf-8")
    r = env["pipe"].run([env["corpus"]])

    assert r.updated == 1
    assert r.created == 0
    after = SourceStore(env["pool"]).get(sid).metadata["source_hash"]
    assert after != before


# --------------------------------------------------------------------------- #
# 3. Deleted source handling                                                  #
# --------------------------------------------------------------------------- #
def test_deleted_source_is_soft_deleted(env):
    p = write(env["corpus"], "a.md", "# A\n\nBody.")
    write(env["corpus"], "b.md", "# B\n\nBody two.")
    env["pipe"].run([env["corpus"]])
    assert SourceStore(env["pool"]).count_active() == 2

    p.unlink()
    r = env["pipe"].run([env["corpus"]])

    assert r.deleted == 1
    assert SourceStore(env["pool"]).count_active() == 1
    sid = _source_id(str(p.resolve()))
    assert SourceStore(env["pool"]).get(sid).is_active is False
    # chunk_map for the deleted source is cleared
    assert _count(env["pool"], "chunk_map", "WHERE source_id = ?", (sid,)) == 0


# --------------------------------------------------------------------------- #
# 4. Malformed files (invalid utf-8)                                          #
# --------------------------------------------------------------------------- #
def test_malformed_file_is_unreadable_not_ingested(env):
    (env["corpus"] / "bad.md").write_bytes(b"\xff\xfe\x00broken\x80")
    write(env["corpus"], "good.md", "# Good\n\nBody.")

    r = env["pipe"].run([env["corpus"]])
    assert r.created == 1
    assert r.census.unreadable_files == 1
    assert SourceStore(env["pool"]).count_active() == 1


# --------------------------------------------------------------------------- #
# 5. Unsupported types                                                        #
# --------------------------------------------------------------------------- #
def test_unsupported_types_are_excluded(env):
    write(env["corpus"], "keep.md", "# Keep\n\nBody.")
    write(env["corpus"], "skip.py", "print('code')")
    write(env["corpus"], "data.json", '{"x": 1}')

    r = env["pipe"].run([env["corpus"]])
    assert r.created == 1
    assert r.census.unsupported_files == 2
    assert set(r.census.unsupported_types) == {".py", ".json"}


# --------------------------------------------------------------------------- #
# 6. Exact-duplicate file (same bytes, different path)                        #
# --------------------------------------------------------------------------- #
def test_exact_duplicate_file_skipped(env):
    body = "# Same\n\nIdentical bytes here."
    write(env["corpus"], "one.md", body)
    write(env["corpus"], "nested/two.md", body)

    r = env["pipe"].run([env["corpus"]])
    assert r.created == 1
    assert r.skipped_duplicate == 1
    assert SourceStore(env["pool"]).count_active() == 1


# --------------------------------------------------------------------------- #
# 7. Chunk ordering persisted                                                 #
# --------------------------------------------------------------------------- #
def test_persisted_chunk_order(env):
    paras = "\n\n".join(f"Section {i} " + "z" * 500 for i in range(5))
    p = write(env["corpus"], "multi.md", paras)
    env["pipe"].run([env["corpus"]])

    sid = _source_id(str(p.resolve()))
    with env["pool"].get_connection() as conn:
        idxs = [r["chunk_index"] for r in conn.execute(
            "SELECT chunk_index FROM chunk_map WHERE source_id=? "
            "ORDER BY chunk_index", (sid,)).fetchall()]
    assert idxs == sorted(idxs)
    assert idxs == list(range(len(idxs)))


# --------------------------------------------------------------------------- #
# 8. Content reconstruction                                                   #
# --------------------------------------------------------------------------- #
def test_content_reconstruction_matches_normalized(env):
    raw = "\n\n".join(f"Para {i} " + "w" * 300 for i in range(6))
    p = write(env["corpus"], "recon.md", raw)
    env["pipe"].run([env["corpus"]])

    sid = _source_id(str(p.resolve()))
    reconstructed = env["pipe"].reconstruct(sid)
    expected = "\n\n".join(c.text for c in chunk_text(normalize_text(raw)))
    assert reconstructed == expected


def test_reconstruction_survives_shared_chunks(env):
    # Two sources sharing an identical chunk still each reconstruct fully.
    shared = "Shared paragraph identical in both."
    write(env["corpus"], "x.md", f"# X\n\n{shared}\n\nUnique to X.")
    write(env["corpus"], "y.md", f"# Y\n\n{shared}\n\nUnique to Y.")
    env["pipe"].run([env["corpus"]])

    sx = _source_id(str((env["corpus"] / "x.md").resolve()))
    sy = _source_id(str((env["corpus"] / "y.md").resolve()))
    rx = env["pipe"].reconstruct(sx)
    ry = env["pipe"].reconstruct(sy)
    assert "Unique to X." in rx and "Unique to Y." in ry
    assert shared in rx and shared in ry


# --------------------------------------------------------------------------- #
# 9. Provenance lookup                                                         #
# --------------------------------------------------------------------------- #
def test_provenance_recorded(env):
    p = write(env["corpus"], "prov.md", "# P\n\nBody.")
    env["pipe"].run([env["corpus"]])
    sid = _source_id(str(p.resolve()))

    meta = SourceStore(env["pool"]).get(sid).metadata
    assert meta["rel_path"] == "prov.md"
    assert meta["source_hash"]
    assert meta["parser_version"]
    assert meta["chunker_version"]

    with env["pool"].get_connection() as conn:
        row = conn.execute(
            "SELECT parser_version, chunker_version FROM chunk_map "
            "WHERE source_id=? LIMIT 1", (sid,)).fetchone()
    assert row["parser_version"] and row["chunker_version"]


def test_ingestion_log_audit_trail(env):
    write(env["corpus"], "a.md", "# A\n\nBody.")
    env["pipe"].run([env["corpus"]])
    assert _count(env["pool"], "ingestion_log", "WHERE action='created'") == 1


# --------------------------------------------------------------------------- #
# 10. Transactional rollback                                                   #
# --------------------------------------------------------------------------- #
def test_transactional_rollback_leaves_no_partial_source(env, monkeypatch):
    write(env["corpus"], "a.md", "# A\n\nGood body paragraph one.\n\nParagraph two.")

    # Force a failure midway through the SQL transaction (during chunk insert).
    import ingestion.pipeline as pl
    real_doc_id = pl._document_id
    calls = {"n": 0}

    def boom(content_hash):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("injected failure mid-transaction")
        return real_doc_id(content_hash)

    monkeypatch.setattr(pl, "_document_id", boom)

    r = env["pipe"].run([env["corpus"]])
    assert r.errors == 1
    assert r.created == 0
    # No partial source row committed.
    assert SourceStore(env["pool"]).count_active() == 0
    assert _count(env["pool"], "sources") == 0
    assert _count(env["pool"], "documents") == 0
    assert _count(env["pool"], "chunk_map") == 0
    assert _count(env["pool"], "ingestion_log", "WHERE action='error'") == 1
