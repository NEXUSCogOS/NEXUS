"""Provenance and versioning for the Librarian ingestion pipeline.

RECOVERED unchanged from the donor at
/Volumes/NEXUS/NEXUS_LOCAL/systems/librarian_rag/ingestion/provenance.py
(commit d855206, "phase 3 - evidence-gated Librarian corpus ingestion").
No fixes needed; part of the 22/22 test baseline.

Every source, document, and chunk carries the exact parser and chunker version
that produced it, so any record can be reproduced or invalidated when a
processing stage changes. These constants are the single source of truth --
bump them when normalization or chunking behavior changes, and re-ingestion
will detect the version drift and re-process affected sources.

Note (F3): this is Librarian's OWN internal ingestion-provenance mechanism
(source_hash / parser_version tracking), distinct from — but designed to
feed into — NEXUS Federation's `provenance.model.ProvenanceRecord` chain
(see `institutional/reporter.py` for how the two connect).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Bump these when the corresponding stage's *behavior* changes.
PARSER_VERSION = "md-text-parser-1.0.0"
NORMALIZER_VERSION = "deterministic-normalizer-1.0.0"
CHUNKER_VERSION = "paragraph-chunker-1.0.0"

# Ingestion-scoped schema: audit log for every ingest action.
INGESTION_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ingestion_log (
    log_id          TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL,
    source_id       TEXT,
    rel_path        TEXT,
    action          TEXT NOT NULL,   -- created|updated|skipped_unchanged|
                                     -- skipped_duplicate|deleted|error
    reason          TEXT,
    source_hash     TEXT,
    parser_version  TEXT,
    chunker_version TEXT,
    documents       INTEGER DEFAULT 0,
    dry_run         INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inglog_run ON ingestion_log(run_id);
CREATE INDEX IF NOT EXISTS idx_inglog_source ON ingestion_log(source_id);
CREATE INDEX IF NOT EXISTS idx_inglog_action ON ingestion_log(action);

-- Links each source's ordered chunks to canonical (possibly shared) chunk
-- content. Many source-chunks may point at one content_hash (dedup), while
-- each source still reconstructs independently via its own ordered rows.
CREATE TABLE IF NOT EXISTS chunk_map (
    source_id       TEXT NOT NULL,
    chunk_index     INTEGER NOT NULL,
    content_hash    TEXT NOT NULL,
    document_id     TEXT NOT NULL,
    tokens          INTEGER NOT NULL,
    parser_version  TEXT NOT NULL,
    chunker_version TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    PRIMARY KEY (source_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunkmap_hash ON chunk_map(content_hash);
CREATE INDEX IF NOT EXISTS idx_chunkmap_source ON chunk_map(source_id);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    """Hash used for chunk-level dedup; matches storage.content_hash semantics."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Hash of raw file bytes; the source-identity / change-detection key."""
    return hashlib.sha256(data).hexdigest()


@dataclass
class Provenance:
    """Immutable record of where a source came from and how it was processed."""

    root: str
    rel_path: str
    abs_path: str
    source_hash: str
    byte_size: int
    mtime: str
    parser_version: str = PARSER_VERSION
    normalizer_version: str = NORMALIZER_VERSION
    chunker_version: str = CHUNKER_VERSION
    discovered_at: str = field(default_factory=utc_now)

    def to_metadata(self) -> dict:
        return {
            "root": self.root,
            "rel_path": self.rel_path,
            "abs_path": self.abs_path,
            "source_hash": self.source_hash,
            "byte_size": self.byte_size,
            "mtime": self.mtime,
            "parser_version": self.parser_version,
            "normalizer_version": self.normalizer_version,
            "chunker_version": self.chunker_version,
            "discovered_at": self.discovered_at,
        }
