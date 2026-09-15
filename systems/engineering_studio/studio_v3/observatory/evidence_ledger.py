"""Evidence Ledger: an append-only, hash-chained SQLite-backed event log.

Part of the Engineering Observatory subsystem (Engineering Studio v4).

Every recorded event is chained to the previous one via a SHA-256 hash over
its canonical JSON representation, making tampering with any stored record
detectable via :meth:`EvidenceLedger.verify_chain`.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

GENESIS_HASH = "0" * 64


class TruncationDetected(Exception):
    """Raised by verify_chain() when the event count no longer matches the
    recorded total_events in _chain_metadata, indicating records were
    deleted (e.g. tail truncation) that would otherwise leave a chain that
    still verifies as internally consistent."""

_COLUMNS = [
    "event_id",
    "timestamp",
    "agent",
    "action",
    "input_data",
    "output_data",
    "test_result",
    "resource_cost",
    "files_modified",
    "git_commit_hash",
    "verification_status",
    "prev_hash",
]

# verification_status is deliberately mutable metadata (written later by
# Task 3's Auditor) and is excluded from the hashed record: the hash covers
# only the original recorded facts, so mutating verification_status must
# never invalidate record_hash or the chain.
_HASHED_COLUMNS = [c for c in _COLUMNS if c != "verification_status"]


class EvidenceLedger:
    """Append-only, hash-chained event ledger backed by SQLite."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None puts sqlite3 in autocommit mode so that we can
        # issue explicit BEGIN IMMEDIATE / COMMIT statements ourselves (see
        # record_event). check_same_thread=False allows the same connection
        # to be shared across threads; correctness across threads is then
        # guaranteed by self._write_lock, while BEGIN IMMEDIATE guarantees
        # correctness across separate processes/connections touching the
        # same SQLite file (SQLite serializes IMMEDIATE writers).
        self._conn = sqlite3.connect(
            str(self.db_path), check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._write_lock = threading.Lock()
        self._create_table()

    def _create_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                agent TEXT NOT NULL,
                action TEXT NOT NULL,
                input_data TEXT,
                output_data TEXT,
                test_result TEXT,
                resource_cost TEXT,
                files_modified TEXT,
                git_commit_hash TEXT,
                verification_status TEXT NOT NULL DEFAULT 'unverified',
                prev_hash TEXT NOT NULL,
                record_hash TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS _chain_metadata (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                total_events INTEGER NOT NULL,
                chain_length_hash TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            INSERT OR IGNORE INTO _chain_metadata (id, total_events, chain_length_hash)
            VALUES (1, 0, ?)
            """,
            (self._compute_chain_length_hash(0, GENESIS_HASH),),
        )
        self._conn.commit()

    @staticmethod
    def _compute_chain_length_hash(total_events: int, last_record_hash: str) -> str:
        canonical = json.dumps(
            {"total_events": total_events, "last_record_hash": last_record_hash},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _canonical_json(record_dict: dict) -> str:
        return json.dumps(record_dict, sort_keys=True, separators=(",", ":"))

    @classmethod
    def _compute_record_hash(cls, record_dict: dict) -> str:
        canonical = cls._canonical_json(record_dict)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _get_last_record_hash(self) -> str:
        row = self._conn.execute(
            "SELECT record_hash FROM events ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return GENESIS_HASH
        return row["record_hash"]

    def record_event(
        self,
        agent: str,
        action: str,
        *,
        input_data=None,
        output_data=None,
        test_result=None,
        resource_cost=None,
        files_modified=None,
        git_commit_hash=None,
    ) -> str:
        event_id = uuid.uuid4().hex

        # Defect E1 fix: reading the current tail hash and appending the new
        # record must be atomic, otherwise two concurrent writers can both
        # read the same prev_hash and fork the chain. self._write_lock
        # serializes concurrent writers within this process (a bare SQLite
        # connection is not safe for concurrent use across threads), and
        # BEGIN IMMEDIATE acquires SQLite's RESERVED lock up front so that
        # any other connection (e.g. another process) attempting a write
        # blocks/retries until this transaction commits, instead of both
        # transactions reading a stale tail hash.
        with self._write_lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                # Generated inside the critical section so that timestamp
                # order matches insertion (and hence chain) order, keeping
                # it consistent with verify_chain()'s ORDER BY.
                timestamp = datetime.now(timezone.utc).isoformat()
                prev_hash = self._get_last_record_hash()

                record_dict = {
                    "event_id": event_id,
                    "timestamp": timestamp,
                    "agent": agent,
                    "action": action,
                    "input_data": json.dumps(input_data) if input_data is not None else None,
                    "output_data": json.dumps(output_data) if output_data is not None else None,
                    "test_result": json.dumps(test_result) if test_result is not None else None,
                    "resource_cost": json.dumps(resource_cost) if resource_cost is not None else None,
                    "files_modified": json.dumps(files_modified) if files_modified is not None else None,
                    "git_commit_hash": git_commit_hash,
                    "verification_status": "unverified",
                    "prev_hash": prev_hash,
                }

                hashed_dict = {k: v for k, v in record_dict.items() if k in _HASHED_COLUMNS}
                record_hash = self._compute_record_hash(hashed_dict)

                self._conn.execute(
                    """
                    INSERT INTO events (
                        event_id, timestamp, agent, action, input_data, output_data,
                        test_result, resource_cost, files_modified, git_commit_hash,
                        verification_status, prev_hash, record_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record_dict["event_id"],
                        record_dict["timestamp"],
                        record_dict["agent"],
                        record_dict["action"],
                        record_dict["input_data"],
                        record_dict["output_data"],
                        record_dict["test_result"],
                        record_dict["resource_cost"],
                        record_dict["files_modified"],
                        record_dict["git_commit_hash"],
                        record_dict["verification_status"],
                        record_dict["prev_hash"],
                        record_hash,
                    ),
                )

                # Update _chain_metadata in the same transaction as the
                # insert so total_events/chain_length_hash can never drift
                # out of sync with the events table (Defect E2 fix).
                row = self._conn.execute(
                    "SELECT total_events FROM _chain_metadata WHERE id = 1"
                ).fetchone()
                new_total = (row["total_events"] if row else 0) + 1
                new_chain_length_hash = self._compute_chain_length_hash(new_total, record_hash)
                self._conn.execute(
                    """
                    UPDATE _chain_metadata
                    SET total_events = ?, chain_length_hash = ?
                    WHERE id = 1
                    """,
                    (new_total, new_chain_length_hash),
                )

                self._conn.commit()
            except BaseException:
                self._conn.rollback()
                raise

        return event_id

    def verify_chain(self) -> tuple[bool, str | None]:
        # Defect E3 fix: the chain is constructed in rowid (insertion) order
        # via prev_hash chaining, not by timestamp. Ordering verification by
        # timestamp breaks whenever clocks are non-monotonic (NTP skew,
        # manual clock adjustment, etc.), producing false-positive breaks.
        # rowid strictly reflects insertion order in SQLite, matching how
        # record_event() actually built the chain.
        rows = self._conn.execute(
            "SELECT * FROM events ORDER BY rowid ASC"
        ).fetchall()

        meta_row = self._conn.execute(
            "SELECT total_events, chain_length_hash FROM _chain_metadata WHERE id = 1"
        ).fetchone()
        expected_total = meta_row["total_events"] if meta_row else 0

        # Defect E2 fix: deleting records (tail or mid-chain) can otherwise
        # leave a chain that still verifies internally (e.g. deleting the
        # tail just makes the chain "end early" with no external anchor to
        # notice). Compare actual event count against the metadata recorded
        # at write time, which is updated atomically with every insert.
        if len(rows) != expected_total:
            raise TruncationDetected(
                f"expected {expected_total} events per _chain_metadata, found {len(rows)}"
            )

        expected_prev_hash = GENESIS_HASH
        last_record_hash = GENESIS_HASH
        for row in rows:
            record_dict = {col: row[col] for col in _HASHED_COLUMNS}
            recomputed_hash = self._compute_record_hash(record_dict)

            if recomputed_hash != row["record_hash"]:
                return (False, row["event_id"])

            if row["prev_hash"] != expected_prev_hash:
                return (False, row["event_id"])

            expected_prev_hash = row["record_hash"]
            last_record_hash = row["record_hash"]

        if meta_row is not None:
            recomputed_chain_length_hash = self._compute_chain_length_hash(
                len(rows), last_record_hash if rows else GENESIS_HASH
            )
            if recomputed_chain_length_hash != meta_row["chain_length_hash"]:
                raise TruncationDetected(
                    "chain_length_hash mismatch: event count matches but the "
                    "recorded chain-length hash does not, indicating records "
                    "were deleted and replaced (e.g. mid-chain truncation)."
                )

        return (True, None)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        result = dict(row)
        for field in ("input_data", "output_data", "test_result", "resource_cost", "files_modified"):
            if result.get(field) is not None:
                result[field] = json.loads(result[field])
        return result

    def get_event(self, event_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM events WHERE event_id = ?", (event_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def query_events(
        self,
        *,
        agent: str | None = None,
        action: str | None = None,
        since: str | None = None,
    ) -> list[dict]:
        clauses = []
        params: list = []
        if agent is not None:
            clauses.append("agent = ?")
            params.append(agent)
        if action is not None:
            clauses.append("action = ?")
            params.append(action)
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)

        query = "SELECT * FROM events"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY timestamp ASC, rowid ASC"

        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def set_verification_status(self, event_id: str, status: str) -> None:
        valid_statuses = {"unverified", "verified", "refuted"}
        if status not in valid_statuses:
            raise ValueError(
                f"Invalid verification_status {status!r}; must be one of {valid_statuses}"
            )
        self._conn.execute(
            "UPDATE events SET verification_status = ? WHERE event_id = ?",
            (status, event_id),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
