"""Tests for CompressionPipeline: strategy selection, real measured
compression ratios, and just-in-time decompression accuracy."""

from __future__ import annotations

import json
import sqlite3
import zipfile

import pytest

from systems.engineering_studio.studio_v4.storage.compression_pipeline import (
    CompressionPipeline,
    CompressionStrategy,
)


@pytest.fixture
def pipeline():
    return CompressionPipeline()


def test_choose_strategy_json_is_gzip(pipeline, tmp_path):
    p = tmp_path / "data.json"
    p.write_text("{}")
    assert pipeline.choose_strategy(p) == CompressionStrategy.GZIP


def test_choose_strategy_sqlite_is_sqlite3_gz(pipeline, tmp_path):
    p = tmp_path / "data.sqlite3"
    p.write_bytes(b"")
    assert pipeline.choose_strategy(p) == CompressionStrategy.SQLITE3_GZ


def test_choose_strategy_directory_is_zip(pipeline, tmp_path):
    d = tmp_path / "bundle"
    d.mkdir()
    assert pipeline.choose_strategy(d, is_bundle=True) == CompressionStrategy.ZIP


def test_compress_gzip_reduces_size_and_is_measured(pipeline, tmp_path):
    src = tmp_path / "big.json"
    dest_dir = tmp_path / "dest"
    payload = json.dumps({"k": "v" * 5000}).encode()
    src.write_bytes(payload)

    result = pipeline.compress(src, dest_dir)

    assert result["strategy"] == "gzip"
    assert result["size_before"] == len(payload)
    assert result["size_after"] < result["size_before"]
    assert result["ratio"] > 0.5  # highly repetitive payload compresses well
    assert (dest_dir / "big.json.gz").exists()


def test_compress_gzip_decompress_jit_round_trips(pipeline, tmp_path):
    src = tmp_path / "notes.txt"
    dest_dir = tmp_path / "dest"
    src.write_text("the quick brown fox " * 200)

    result = pipeline.compress(src, dest_dir)
    recovered = pipeline.decompress_jit(result["compressed_path"])

    assert recovered == src.read_bytes()


def test_compress_zip_directory_and_jit_extract_one_member(pipeline, tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "a.txt").write_text("aaaa")
    (bundle / "b.txt").write_text("bbbb")
    dest_dir = tmp_path / "dest"

    result = pipeline.compress(bundle, dest_dir, strategy=CompressionStrategy.ZIP)

    assert result["strategy"] == "zip"
    with zipfile.ZipFile(result["compressed_path"]) as zf:
        members = zf.namelist()
    assert any(m.endswith("a.txt") for m in members)
    assert any(m.endswith("b.txt") for m in members)

    a_member = [m for m in members if m.endswith("a.txt")][0]
    recovered = pipeline.decompress_jit(result["compressed_path"], member_name=a_member)
    assert recovered == b"aaaa"


def test_compress_sqlite_gz_and_decompress_jit_to_file_is_queryable(pipeline, tmp_path):
    db_path = tmp_path / "test.sqlite3"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE t (id INTEGER, val TEXT)")
    conn.executemany("INSERT INTO t VALUES (?, ?)", [(i, f"row{i}") for i in range(50)])
    conn.commit()
    conn.close()

    dest_dir = tmp_path / "dest"
    result = pipeline.compress(db_path, dest_dir, strategy=CompressionStrategy.SQLITE3_GZ)

    assert result["strategy"] == "sqlite3_gz"
    assert result["size_after"] > 0

    restore_dir = tmp_path / "restore"
    restored_path = pipeline.decompress_jit_to_file(
        result["compressed_path"], restore_dir, member_name="restored.sqlite3"
    )
    conn2 = sqlite3.connect(str(restored_path))
    rows = conn2.execute("SELECT COUNT(*) FROM t").fetchone()
    conn2.close()
    assert rows[0] == 50


def test_compress_ratio_and_saved_bytes_are_consistent(pipeline, tmp_path):
    src = tmp_path / "data.json"
    src.write_text(json.dumps({"repeat": "z" * 20000}))
    dest_dir = tmp_path / "dest"

    result = pipeline.compress(src, dest_dir)

    assert result["saved_bytes"] == result["size_before"] - result["size_after"]
    assert result["ratio"] == pytest.approx(
        result["saved_bytes"] / result["size_before"], rel=1e-9
    )


def test_decompress_jit_multi_member_zip_requires_member_name(pipeline, tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "a.txt").write_text("aaaa")
    (bundle / "b.txt").write_text("bbbb")
    dest_dir = tmp_path / "dest"

    result = pipeline.compress(bundle, dest_dir, strategy=CompressionStrategy.ZIP)

    with pytest.raises(ValueError):
        pipeline.decompress_jit(result["compressed_path"])
