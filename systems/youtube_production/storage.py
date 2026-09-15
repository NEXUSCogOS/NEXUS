"""YouTube Production persistence. NEXUS Federation F8.

SQLite, versioned where mission section 29 (idempotency) requires it.
Metadata (missions, evidence packs, claim ledgers, fact-check results,
render records, reports) is stored in a small local `.db` file (already
globally gitignored, per this estate's convention -- see .gitignore's
`*.db` rule). Actual media bytes (rendered video, thumbnail images, audio)
are written EXTERNAL-FIRST to the mounted external volume
(`/Volumes/NEXUS/NEXUS_LOCAL/f8_media_output/`), never bulk-stored inside
the internal Mac disk or committed to git -- mission section 31. If the
external volume is unavailable, storage falls back to a clearly-marked
local scratch directory and reports `external_dependency=True,
external_bytes=None` rather than silently writing large media to the
internal disk without disclosure.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

EXTERNAL_MEDIA_ROOT = Path("/Volumes/NEXUS/NEXUS_LOCAL/f8_media_output")
LOCAL_FALLBACK_MEDIA_ROOT = Path(__file__).resolve().parent / "data" / "local_fallback_media"


def media_output_dir() -> tuple[Path, bool]:
    """Returns (dir, is_external). Never silently substitutes local
    storage without the caller being told via is_external=False."""
    try:
        EXTERNAL_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
        probe = EXTERNAL_MEDIA_ROOT / ".write_probe"
        probe.write_text("ok")
        probe.unlink()
        return EXTERNAL_MEDIA_ROOT, True
    except Exception:
        LOCAL_FALLBACK_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
        return LOCAL_FALLBACK_MEDIA_ROOT, False


SCHEMA = """
CREATE TABLE IF NOT EXISTS production_missions (
    production_mission_id TEXT PRIMARY KEY,
    parent_trigger_id TEXT,
    parent_synthesis_id TEXT,
    channel_id TEXT,
    editorial_objective TEXT NOT NULL,
    contract_json TEXT NOT NULL,
    terminal_state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_packs (
    evidence_pack_id TEXT PRIMARY KEY,
    production_mission_id TEXT NOT NULL,
    pack_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (production_mission_id) REFERENCES production_missions(production_mission_id)
);

CREATE TABLE IF NOT EXISTS claim_ledgers (
    production_mission_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    entry_json TEXT NOT NULL,
    PRIMARY KEY (production_mission_id, claim_id)
);

CREATE TABLE IF NOT EXISTS scripts (
    script_id TEXT PRIMARY KEY,
    production_mission_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    script_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_check_results (
    production_mission_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    result_json TEXT NOT NULL,
    PRIMARY KEY (production_mission_id, claim_id)
);

CREATE TABLE IF NOT EXISTS rights_records (
    production_mission_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    record_json TEXT NOT NULL,
    PRIMARY KEY (production_mission_id, asset_id)
);

CREATE TABLE IF NOT EXISTS render_records (
    production_mission_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    render_json TEXT NOT NULL,
    PRIMARY KEY (production_mission_id, revision)
);

CREATE TABLE IF NOT EXISTS thumbnails (
    production_mission_id TEXT PRIMARY KEY,
    thumbnail_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metadata_records (
    production_mission_id TEXT PRIMARY KEY,
    metadata_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS production_reports (
    production_mission_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    report_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (production_mission_id, cycle_id)
);

CREATE TABLE IF NOT EXISTS observability_counters (
    counter_name TEXT PRIMARY KEY,
    counter_value INTEGER NOT NULL DEFAULT 0
);
"""


class YouTubeProductionStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # -- Missions -------------------------------------------------------

    def find_mission(self, production_mission_id: str) -> Optional[dict]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM production_missions WHERE production_mission_id = ?",
                (production_mission_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def upsert_mission(self, contract, terminal_state: str, created_at: str, updated_at: str) -> bool:
        """Returns True if this was a NEW insert, False if it already existed
        (idempotency signal for mission section 29)."""
        existing = self.find_mission(contract.production_mission_id)
        conn = self._connect()
        try:
            if existing is None:
                conn.execute(
                    """INSERT INTO production_missions
                       (production_mission_id, parent_trigger_id, parent_synthesis_id,
                        channel_id, editorial_objective, contract_json, terminal_state,
                        created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        contract.production_mission_id,
                        contract.parent_trigger_id,
                        contract.parent_synthesis_id,
                        contract.channel_id,
                        contract.editorial_objective,
                        json.dumps(contract.__dict__),
                        terminal_state,
                        created_at,
                        updated_at,
                    ),
                )
                conn.commit()
                return True
            else:
                conn.execute(
                    "UPDATE production_missions SET terminal_state=?, updated_at=? WHERE production_mission_id=?",
                    (terminal_state, updated_at, contract.production_mission_id),
                )
                conn.commit()
                return False
        finally:
            conn.close()

    def set_terminal_state(self, production_mission_id: str, terminal_state: str, updated_at: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE production_missions SET terminal_state=?, updated_at=? WHERE production_mission_id=?",
                (terminal_state, updated_at, production_mission_id),
            )
            conn.commit()
        finally:
            conn.close()

    # -- Evidence pack / claim ledger ------------------------------------

    def save_evidence_pack(self, pack) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO evidence_packs (evidence_pack_id, production_mission_id, pack_json, created_at) VALUES (?, ?, ?, ?)",
                (pack.evidence_pack_id, pack.production_mission_id, json.dumps(_dc(pack)), pack.created_at),
            )
            conn.commit()
        finally:
            conn.close()

    def find_evidence_pack(self, production_mission_id: str) -> Optional[dict]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT pack_json FROM evidence_packs WHERE production_mission_id = ?",
                (production_mission_id,),
            ).fetchone()
            return json.loads(row["pack_json"]) if row else None
        finally:
            conn.close()

    def save_claim_ledger(self, production_mission_id: str, entries: list) -> None:
        conn = self._connect()
        try:
            for e in entries:
                conn.execute(
                    "INSERT OR REPLACE INTO claim_ledgers (production_mission_id, claim_id, entry_json) VALUES (?, ?, ?)",
                    (production_mission_id, e.claim_id, json.dumps(_dc(e))),
                )
            conn.commit()
        finally:
            conn.close()

    def find_claim_ledger(self, production_mission_id: str) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT entry_json FROM claim_ledgers WHERE production_mission_id = ?",
                (production_mission_id,),
            ).fetchall()
            return [json.loads(r["entry_json"]) for r in rows]
        finally:
            conn.close()

    # -- Script -----------------------------------------------------------

    def save_script(self, script) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO scripts (script_id, production_mission_id, revision, script_json, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
                (script.script_id, script.production_mission_id, script.revision, json.dumps(_dc(script))),
            )
            conn.commit()
        finally:
            conn.close()

    def find_latest_script(self, production_mission_id: str) -> Optional[dict]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT script_json FROM scripts WHERE production_mission_id = ? ORDER BY revision DESC LIMIT 1",
                (production_mission_id,),
            ).fetchone()
            return json.loads(row["script_json"]) if row else None
        finally:
            conn.close()

    # -- Fact-check ---------------------------------------------------------

    def save_fact_check_results(self, production_mission_id: str, results: list) -> None:
        conn = self._connect()
        try:
            for r in results:
                conn.execute(
                    "INSERT OR REPLACE INTO fact_check_results (production_mission_id, claim_id, result_json) VALUES (?, ?, ?)",
                    (production_mission_id, r.claim_id, json.dumps(_dc(r))),
                )
            conn.commit()
        finally:
            conn.close()

    # -- Rights -------------------------------------------------------------

    def save_rights_record(self, production_mission_id: str, record) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO rights_records (production_mission_id, asset_id, record_json) VALUES (?, ?, ?)",
                (production_mission_id, record.asset_id, json.dumps(_dc(record))),
            )
            conn.commit()
        finally:
            conn.close()

    def find_rights_records(self, production_mission_id: str) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT record_json FROM rights_records WHERE production_mission_id = ?",
                (production_mission_id,),
            ).fetchall()
            return [json.loads(r["record_json"]) for r in rows]
        finally:
            conn.close()

    # -- Render -------------------------------------------------------------

    def find_latest_render(self, production_mission_id: str) -> Optional[dict]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT render_json FROM render_records WHERE production_mission_id = ? ORDER BY revision DESC LIMIT 1",
                (production_mission_id,),
            ).fetchone()
            return json.loads(row["render_json"]) if row else None
        finally:
            conn.close()

    def save_render_record(self, record) -> bool:
        """Returns True if this revision was newly inserted (idempotency:
        replaying the same mission+revision must not create a duplicate)."""
        conn = self._connect()
        try:
            existing = conn.execute(
                "SELECT 1 FROM render_records WHERE production_mission_id=? AND revision=?",
                (record.production_mission_id, record.revision),
            ).fetchone()
            if existing:
                return False
            conn.execute(
                "INSERT INTO render_records (production_mission_id, revision, render_json) VALUES (?, ?, ?)",
                (record.production_mission_id, record.revision, json.dumps(_dc(record))),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    # -- Thumbnail / metadata -------------------------------------------------

    def save_thumbnail(self, thumb) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO thumbnails (production_mission_id, thumbnail_json) VALUES (?, ?)",
                (thumb.production_mission_id, json.dumps(_dc(thumb))),
            )
            conn.commit()
        finally:
            conn.close()

    def save_metadata(self, production_mission_id: str, metadata) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO metadata_records (production_mission_id, metadata_json) VALUES (?, ?)",
                (production_mission_id, json.dumps(_dc(metadata))),
            )
            conn.commit()
        finally:
            conn.close()

    # -- Reports --------------------------------------------------------------

    def save_report(self, production_mission_id: str, cycle_id: str, report: dict, created_at: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO production_reports (production_mission_id, cycle_id, report_json, created_at) VALUES (?, ?, ?, ?)",
                (production_mission_id, cycle_id, json.dumps(report), created_at),
            )
            conn.commit()
        finally:
            conn.close()

    def find_latest_report(self, production_mission_id: str) -> Optional[dict]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT report_json FROM production_reports WHERE production_mission_id = ? ORDER BY created_at DESC LIMIT 1",
                (production_mission_id,),
            ).fetchone()
            return json.loads(row["report_json"]) if row else None
        finally:
            conn.close()

    # -- Observability counters ----------------------------------------------

    def increment_counter(self, name: str, by: int = 1) -> int:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO observability_counters (counter_name, counter_value) VALUES (?, ?) "
                "ON CONFLICT(counter_name) DO UPDATE SET counter_value = counter_value + ?",
                (name, by, by),
            )
            conn.commit()
            row = conn.execute(
                "SELECT counter_value FROM observability_counters WHERE counter_name = ?", (name,)
            ).fetchone()
            return row["counter_value"] if row else 0
        finally:
            conn.close()

    def all_counters(self) -> dict:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT counter_name, counter_value FROM observability_counters").fetchall()
            return {r["counter_name"]: r["counter_value"] for r in rows}
        finally:
            conn.close()


def _dc(obj) -> dict:
    """dataclass -> plain dict, recursively enough for our nested lists of dataclasses."""
    if hasattr(obj, "__dict__"):
        out = {}
        for k, v in obj.__dict__.items():
            if isinstance(v, list):
                out[k] = [_dc(x) if hasattr(x, "__dict__") else x for x in v]
            else:
                out[k] = v
        return out
    return obj
