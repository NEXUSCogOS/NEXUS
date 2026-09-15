"""News Intelligence storage. NEXUS Federation F7, mission section 21.

External-first: this SQLite file lives outside git (matches this
estate's *.db policy) and is the FULL store -- both the compact local-hot
index (source_items metadata, event index, source_health, leases) and
the EXTERNAL_ACTIVE content (article bodies/descriptions, full event
records) are columns in the same local SQLite file, not split across a
separate object store, because F7's real volume (tens of items per
acquisition run against two bounded sources) does not yet justify a
second storage system -- this is stated explicitly as a scope decision,
not a silent shortcut. Nothing is bulk-stored in git: this .db file
matches the existing global `*.db` gitignore pattern.

Superseded article versions (corrections) are preserved as new rows,
never overwritten in place (mission section 8's explicit instruction).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS source_items (
    source_item_id TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    canonical_url TEXT NOT NULL,
    publisher TEXT NOT NULL,
    source_class TEXT NOT NULL,
    author TEXT NOT NULL,
    publication_timestamp TEXT,
    retrieval_timestamp TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    headline TEXT NOT NULL,
    language TEXT NOT NULL,
    geography TEXT NOT NULL,
    external_identifiers TEXT NOT NULL,
    retrieval_method TEXT NOT NULL,
    license_access_status TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    raw_description TEXT,
    PRIMARY KEY (source_item_id, version)
);
CREATE INDEX IF NOT EXISTS idx_source_items_hash ON source_items(content_hash);
CREATE INDEX IF NOT EXISTS idx_source_items_url ON source_items(canonical_url);

CREATE TABLE IF NOT EXISTS source_health_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    last_success TEXT,
    latency_seconds REAL,
    http_status INTEGER,
    parse_success INTEGER NOT NULL,
    item_yield INTEGER NOT NULL,
    rate_limited INTEGER NOT NULL,
    auth_required INTEGER NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    event_type TEXT NOT NULL,
    headline_summary TEXT NOT NULL,
    entities_json TEXT NOT NULL,
    locations_json TEXT NOT NULL,
    event_time TEXT,
    publication_time TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    source_ids_json TEXT NOT NULL,
    source_count INTEGER NOT NULL,
    independent_source_count INTEGER NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    provenance_refs_json TEXT NOT NULL,
    novelty TEXT NOT NULL,
    materiality_json TEXT NOT NULL,
    uncertainty_json TEXT NOT NULL,
    freshness TEXT NOT NULL,
    status TEXT NOT NULL,
    claim_epistemology TEXT NOT NULL,
    cluster_id TEXT,
    PRIMARY KEY (event_id, version)
);
CREATE INDEX IF NOT EXISTS idx_events_cluster ON events(cluster_id);

CREATE TABLE IF NOT EXISTS acquisition_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    items_fetched INTEGER NOT NULL DEFAULT 0,
    items_accepted INTEGER NOT NULL DEFAULT 0,
    items_rejected INTEGER NOT NULL DEFAULT 0,
    duplicates INTEGER NOT NULL DEFAULT 0,
    near_duplicates INTEGER NOT NULL DEFAULT 0,
    events_created INTEGER NOT NULL DEFAULT 0,
    events_updated INTEGER NOT NULL DEFAULT 0,
    source_failures INTEGER NOT NULL DEFAULT 0
);
"""


class NewsStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        with conn:
            conn.executescript(SCHEMA)
        conn.close()

    # ---- canonical identity / dedup (mission sections 8, 9) ----------

    def find_existing_source_item(self, source_item_id: str) -> Optional[dict]:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM source_items WHERE source_item_id=? ORDER BY version DESC LIMIT 1",
            (source_item_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def find_by_content_hash(self, content_hash: str) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM source_items WHERE content_hash=?", (content_hash,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def store_source_item(self, item, is_update: bool = False) -> int:
        """Returns the version number written. A genuine update (content
        changed under the same source_item_id) is stored as version+1,
        never an overwrite -- mission section 8."""
        conn = self._connect()
        existing = conn.execute(
            "SELECT MAX(version) FROM source_items WHERE source_item_id=?",
            (item.source_item_id,),
        ).fetchone()[0]
        version = (existing or 0) + 1
        with conn:
            conn.execute(
                """INSERT INTO source_items
                   (source_item_id, version, canonical_url, publisher, source_class,
                    author, publication_timestamp, retrieval_timestamp, content_hash,
                    headline, language, geography, external_identifiers,
                    retrieval_method, license_access_status, verification_status,
                    raw_description)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    item.source_item_id, version, item.canonical_url, item.publisher,
                    item.source_class.value, item.author, item.publication_timestamp,
                    item.retrieval_timestamp, item.content_hash, item.headline,
                    item.language, item.geography, json.dumps(item.external_identifiers),
                    item.retrieval_method, item.license_access_status,
                    item.verification_status, item.raw_description,
                ),
            )
        conn.close()
        return version

    def count_source_items(self) -> int:
        conn = self._connect()
        n = conn.execute("SELECT COUNT(DISTINCT source_item_id) FROM source_items").fetchone()[0]
        conn.close()
        return n

    # ---- source health (mission section 7) ---------------------------

    def log_source_health(self, health, checked_at: str) -> None:
        conn = self._connect()
        with conn:
            conn.execute(
                """INSERT INTO source_health_log
                   (source_id, checked_at, last_success, latency_seconds, http_status,
                    parse_success, item_yield, rate_limited, auth_required, status)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    health.source_id, checked_at, health.last_success,
                    health.latency_seconds, health.http_status,
                    int(health.parse_success), health.item_yield,
                    int(health.rate_limited), int(health.auth_required),
                    health.status.value,
                ),
            )
        conn.close()

    def latest_source_health(self, source_id: str) -> Optional[dict]:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM source_health_log WHERE source_id=? ORDER BY id DESC LIMIT 1",
            (source_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    # ---- events (mission section 12) ----------------------------------

    def find_event_by_id(self, event_id: str) -> Optional[dict]:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM events WHERE event_id=? ORDER BY version DESC LIMIT 1",
            (event_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def all_events(self) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM events e WHERE version = (SELECT MAX(version) FROM events WHERE event_id=e.event_id)"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def store_event(self, event) -> int:
        conn = self._connect()
        existing = conn.execute(
            "SELECT MAX(version) FROM events WHERE event_id=?", (event.event_id,)
        ).fetchone()[0]
        version = (existing or 0) + 1
        with conn:
            conn.execute(
                """INSERT INTO events
                   (event_id, version, event_type, headline_summary, entities_json,
                    locations_json, event_time, publication_time, first_seen, last_seen,
                    source_ids_json, source_count, independent_source_count,
                    evidence_refs_json, provenance_refs_json, novelty, materiality_json,
                    uncertainty_json, freshness, status, claim_epistemology, cluster_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    event.event_id, version, event.event_type.value, event.headline_summary,
                    json.dumps([e.__dict__ | {"entity_type": e.entity_type.value, "resolution_state": e.resolution_state.value} for e in event.entities]),
                    json.dumps(event.locations), event.event_time, event.publication_time,
                    event.first_seen, event.last_seen, json.dumps(event.source_ids),
                    event.source_count, event.independent_source_count,
                    json.dumps(event.evidence_refs), json.dumps(event.provenance_refs),
                    event.novelty.value, json.dumps(event.materiality),
                    json.dumps(event.uncertainty), event.freshness, event.status.value,
                    event.claim_epistemology.value, event.cluster_id,
                ),
            )
        conn.close()
        return version

    def count_events(self) -> int:
        conn = self._connect()
        n = conn.execute("SELECT COUNT(DISTINCT event_id) FROM events").fetchone()[0]
        conn.close()
        return n
