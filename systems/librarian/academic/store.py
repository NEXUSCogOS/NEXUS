"""Academic corpus store — SEPARATE from the internal NEXUS documentation
corpus (`corpus/database.py`'s `librarian.db`), per the mission's explicit
requirement (section 23) that the two must not be conflated.

NEW module, NEXUS Librarian F4. A dedicated SQLite file
(`data/academic_corpus.db`) with its own schema: `academic_sources`
(current state per source), `academic_source_events` (append-only:
retraction/correction/version history — a retraction is recorded as an
EVENT, never a silent overwrite of the prior ACTIVE state), and
`citation_edges` (the citation graph, F4).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS academic_sources (
    source_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    authors TEXT NOT NULL,
    publication_date TEXT NOT NULL,
    journal_or_venue TEXT NOT NULL,
    publisher TEXT NOT NULL,
    doi TEXT NOT NULL,
    external_identifiers TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    source_type TEXT NOT NULL,
    peer_review_status TEXT NOT NULL,
    retrieval_timestamp TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    license TEXT NOT NULL,
    language TEXT NOT NULL,
    version TEXT NOT NULL,
    retraction_status TEXT NOT NULL,
    correction_status TEXT NOT NULL,
    ingestion_method TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    retrievable_text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_academic_source_type ON academic_sources(source_type);
CREATE INDEX IF NOT EXISTS idx_academic_retraction ON academic_sources(retraction_status);
CREATE INDEX IF NOT EXISTS idx_academic_doi ON academic_sources(doi);
CREATE INDEX IF NOT EXISTS idx_academic_content_hash ON academic_sources(content_hash);
CREATE INDEX IF NOT EXISTS idx_academic_canonical_url ON academic_sources(canonical_url);
CREATE INDEX IF NOT EXISTS idx_academic_publication_date ON academic_sources(publication_date);
CREATE INDEX IF NOT EXISTS idx_academic_verification ON academic_sources(verification_status);

CREATE TABLE IF NOT EXISTS academic_source_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    event_type TEXT NOT NULL,   -- INGESTED | RETRACTED | CORRECTED | SUPERSEDED | VERIFIED | REVERIFIED
    detail TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_academic_events_source ON academic_source_events(source_id);

CREATE TABLE IF NOT EXISTS citation_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_from TEXT NOT NULL,
    source_to TEXT NOT NULL,
    edge_type TEXT NOT NULL,   -- CITES | CITED_BY | SUPPORTS | CONTRADICTS | EXTENDS | REPLICATES | CORRECTS | RETRACTS
    evidence TEXT NOT NULL,    -- what justifies this edge -- required, never blank
    verified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(source_from, source_to, edge_type)
);
CREATE INDEX IF NOT EXISTS idx_citation_from ON citation_edges(source_from);
CREATE INDEX IF NOT EXISTS idx_citation_to ON citation_edges(source_to);
CREATE INDEX IF NOT EXISTS idx_citation_verified ON citation_edges(verified);
"""


class AcademicStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ---- sources ------------------------------------------------------

    def upsert_source(self, record: dict[str, Any]) -> bool:
        """Insert a new source, or no-op if the source_id already exists
        (use `record_event` + a dedicated update method for state
        transitions like retraction -- upsert never silently overwrites
        an existing source's retraction/correction state)."""
        with self.connection() as conn:
            existing = conn.execute(
                "SELECT 1 FROM academic_sources WHERE source_id = ?", (record["source_id"],)
            ).fetchone()
            if existing:
                return False
            conn.execute(
                """INSERT INTO academic_sources (
                    source_id, title, authors, publication_date, journal_or_venue,
                    publisher, doi, external_identifiers, canonical_url, source_type,
                    peer_review_status, retrieval_timestamp, content_hash, license,
                    language, version, retraction_status, correction_status,
                    ingestion_method, verification_status, retrievable_text, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record["source_id"], record["title"], json.dumps(record["authors"]),
                    record["publication_date"], record["journal_or_venue"], record["publisher"],
                    record["doi"], json.dumps(record["external_identifiers"]), record["canonical_url"],
                    record["source_type"], record["peer_review_status"], record["retrieval_timestamp"],
                    record["content_hash"], record["license"], record["language"], record["version"],
                    record["retraction_status"], record["correction_status"], record["ingestion_method"],
                    record["verification_status"], record["retrievable_text"],
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            return True

    def get_source(self, source_id: str) -> Optional[dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM academic_sources WHERE source_id = ?", (source_id,)).fetchone()
            return self._row_to_dict(row) if row else None

    def get_by_doi(self, doi: str) -> Optional[dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM academic_sources WHERE doi = ? AND doi != 'UNKNOWN'", (doi,)).fetchone()
            return self._row_to_dict(row) if row else None

    def all_sources(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM academic_sources ORDER BY created_at").fetchall()
            return [self._row_to_dict(r) for r in rows]

    def get_sources_by_ids(self, source_ids: list[str]) -> list[dict[str, Any]]:
        """Return a deterministic subset without interpolating values into SQL."""
        if not source_ids:
            return []
        placeholders = ",".join("?" for _ in source_ids)
        with self.connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM academic_sources WHERE source_id IN ({placeholders}) ORDER BY created_at",
                source_ids,
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def fts_candidate_ids(self, terms: list[str], limit: int = 500) -> Optional[list[str]]:
        """Use the optional FTS5 acceleration index; None means unavailable.

        Retrieval still applies the original deterministic lexical scorer to
        these candidates, so the index accelerates selection without changing
        the evidence-ranking contract.
        """
        if not terms:
            return []
        expression = " OR ".join('"' + t.replace('"', '""') + '"' for t in terms)
        try:
            with self.connection() as conn:
                rows = conn.execute(
                    "SELECT source_id FROM academic_sources_fts WHERE academic_sources_fts MATCH ? LIMIT ?",
                    (expression, limit),
                ).fetchall()
                return [r[0] for r in rows]
        except sqlite3.OperationalError:
            return None

    def set_retraction_status(self, source_id: str, status: str, *, detail: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE academic_sources SET retraction_status = ? WHERE source_id = ?",
                (status, source_id),
            )
        self.record_event(source_id, event_type=status, detail=detail)

    def record_event(self, source_id: str, *, event_type: str, detail: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO academic_source_events (source_id, event_type, detail, recorded_at) VALUES (?,?,?,?)",
                (source_id, event_type, detail, datetime.now(timezone.utc).isoformat()),
            )

    def get_events(self, source_id: str) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT event_type, detail, recorded_at FROM academic_source_events "
                "WHERE source_id = ? ORDER BY id ASC",
                (source_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ---- citation graph -------------------------------------------------

    def add_citation_edge(self, *, source_from: str, source_to: str, edge_type: str, evidence: str, verified: bool) -> bool:
        if not evidence or not evidence.strip():
            raise ValueError("a citation edge requires non-empty evidence -- never derived from existence alone")
        with self.connection() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO citation_edges (source_from, source_to, edge_type, evidence, verified, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (source_from, source_to, edge_type, evidence, 1 if verified else 0, datetime.now(timezone.utc).isoformat()),
            )
            return cursor.rowcount == 1

    def get_edges_for(self, source_id: str) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT source_from, source_to, edge_type, evidence, verified FROM citation_edges "
                "WHERE source_from = ? OR source_to = ?",
                (source_id, source_id),
            ).fetchall()
            return [dict(r) for r in rows]

    def count_edges(self) -> int:
        with self.connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM citation_edges").fetchone()[0]

    def count_sources(self, **filters: Any) -> int:
        query = "SELECT COUNT(*) FROM academic_sources WHERE 1=1"
        params: list[Any] = []
        for col, val in filters.items():
            query += f" AND {col} = ?"
            params.append(val)
        with self.connection() as conn:
            return conn.execute(query, params).fetchone()[0]

    @staticmethod
    def _row_to_dict(row) -> dict[str, Any]:
        d = dict(row)
        d["authors"] = json.loads(d["authors"])
        d["external_identifiers"] = json.loads(d["external_identifiers"])
        return d
