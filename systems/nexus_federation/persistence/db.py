"""Persistent store for the NEXUS federation substrate.

New module, NEXUS Federation F1. SQLite-backed (consistent with the rest
of this NEXUS estate's control-plane storage choices). Three tables:

- institution_registry: one row per institution, the LATEST accepted state
  (overwritten only when a new report is genuinely accepted -- see
  kernel.py for the accept/reject decision this table reflects).
- report_log: append-only. Every report NEXUS was asked to ingest, whether
  accepted, rejected, or a duplicate/stale/out-of-order/skew-rejected
  no-op -- the full history, never deleted, is the basis for restart
  recovery and for observability counters (which are DERIVED by querying
  this log, never a separately-mutated counter that could drift from
  reality).
- delegation_log: append-only. Every delegation proposal ever generated.
  Carries a UNIQUE `idempotency_key` (NEXUS Federation F2) so the same
  accepted report + the same executive rule can never produce two
  semantically identical delegations, including across a process restart.
- evidence_baseline: (institution, ref) -> first-seen sha256, for drift
  detection across resolutions of the same evidence_ref over time.
- evidence_resolution_ledger: (NEXUS Federation F2) append-only. Every
  resolution ATTEMPT, not just the first-seen baseline -- a full audit
  trail, so a failed resolution is never silently overwritten by a later
  successful one; each attempt is its own immutable row.
- provenance_record: (NEXUS Federation F2) append-only, keyed by
  provenance_id. No UPDATE method exists on this table by design --
  a provenance record, once written, is never mutated.
- state_event_log: (NEXUS Federation F2) append-only. One row per
  capability-state transition per ingest cycle, independent of and in
  addition to the materialized `institution_registry` "current state" --
  sufficient to reconstruct "what did NEXUS believe about capability X at
  cycle N, and why."

Restart recovery is "free" by construction: nothing here is held only in
process memory. A fresh process re-reads the same SQLite file and sees
exactly what was last committed.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS institution_registry (
    institution_id TEXT PRIMARY KEY,
    registry_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    institution_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    report_timestamp TEXT NOT NULL,
    received_at TEXT NOT NULL,
    temporal_classification TEXT NOT NULL,
    accepted INTEGER NOT NULL,
    reason TEXT NOT NULL,
    report_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_report_log_institution ON report_log(institution_id);
CREATE INDEX IF NOT EXISTS idx_report_log_cycle ON report_log(institution_id, cycle_id);

CREATE TABLE IF NOT EXISTS delegation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id TEXT NOT NULL UNIQUE,
    idempotency_key TEXT NOT NULL UNIQUE,
    parent_mission TEXT NOT NULL,
    recipient TEXT NOT NULL,
    created_at TEXT NOT NULL,
    proposal_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_baseline (
    institution_id TEXT NOT NULL,
    ref TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    PRIMARY KEY (institution_id, ref)
);

CREATE TABLE IF NOT EXISTS evidence_resolution_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resolution_id TEXT NOT NULL UNIQUE,
    timestamp TEXT NOT NULL,
    institution TEXT NOT NULL,
    mission_id TEXT,
    cycle_id TEXT NOT NULL,
    evidence_ref TEXT NOT NULL,
    expected_hash TEXT,
    observed_hash TEXT,
    existence INTEGER NOT NULL,
    verification_result TEXT NOT NULL,
    reason TEXT NOT NULL,
    resolver_version TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_ledger_ref ON evidence_resolution_ledger(institution, evidence_ref);

CREATE TABLE IF NOT EXISTS provenance_record (
    provenance_id TEXT PRIMARY KEY,
    record_json TEXT NOT NULL,
    ingestion_timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS state_event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    institution_id TEXT NOT NULL,
    capability_name TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    prior_lifecycle TEXT,
    new_lifecycle TEXT NOT NULL,
    executive_state_class TEXT NOT NULL,
    temporal_classification TEXT NOT NULL,
    transition_reason TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_state_event_institution_cap ON state_event_log(institution_id, capability_name);

CREATE TABLE IF NOT EXISTS delegation_delivery_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id TEXT NOT NULL UNIQUE,
    recipient TEXT NOT NULL,
    delivered_at TEXT NOT NULL,
    executed_at TEXT,
    result_cycle_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_delivery_recipient ON delegation_delivery_log(recipient);

CREATE TABLE IF NOT EXISTS observability_event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    detail TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_observability_event_type ON observability_event_log(event_type);

CREATE TABLE IF NOT EXISTS mission_lifecycle_event (
    event_id TEXT PRIMARY KEY,
    delegation_id TEXT NOT NULL,
    previous_state TEXT,
    new_state TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    evidence_refs_json TEXT,
    provenance_refs_json TEXT,
    lease_id TEXT,
    retry_count INTEGER,
    detail_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_mission_lifecycle_delegation ON mission_lifecycle_event(delegation_id);
CREATE INDEX IF NOT EXISTS idx_mission_lifecycle_state ON mission_lifecycle_event(new_state);
CREATE INDEX IF NOT EXISTS idx_mission_lifecycle_timestamp ON mission_lifecycle_event(timestamp);

CREATE TABLE IF NOT EXISTS mission_dependency (
    dependency_id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL,
    depends_on_mission_id TEXT NOT NULL,
    dependency_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    evidence_refs_json TEXT,
    provenance_refs_json TEXT,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_mission_dependency_mission ON mission_dependency(mission_id);
CREATE INDEX IF NOT EXISTS idx_mission_dependency_prerequisite ON mission_dependency(depends_on_mission_id);
CREATE INDEX IF NOT EXISTS idx_mission_dependency_type ON mission_dependency(dependency_type);

CREATE TABLE IF NOT EXISTS institution_capacity (
    institution_id TEXT PRIMARY KEY,
    availability_state TEXT NOT NULL DEFAULT 'UNKNOWN',
    max_concurrent_missions INTEGER NOT NULL DEFAULT 5,
    active_missions INTEGER NOT NULL DEFAULT 0,
    queued_missions INTEGER NOT NULL DEFAULT 0,
    cpu_pressure_percent REAL DEFAULT 0.0,
    memory_pressure_percent REAL DEFAULT 0.0,
    storage_pressure_percent REAL DEFAULT 0.0,
    api_pressure_percent REAL DEFAULT 0.0,
    circuit_state TEXT NOT NULL DEFAULT 'CLOSED',
    last_heartbeat TEXT,
    last_successful_cycle TEXT,
    updated_at TEXT NOT NULL,
    policy_version TEXT NOT NULL DEFAULT 'F9.0'
);

CREATE TABLE IF NOT EXISTS mission_outcome (
    outcome_id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL,
    delegation_id TEXT NOT NULL,
    outcome_class TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    evaluator TEXT NOT NULL DEFAULT 'nexus_kernel',
    objective TEXT,
    success_criteria_json TEXT,
    criteria_met_json TEXT,
    criteria_unmet_json TEXT,
    evidence_refs_json TEXT,
    provenance_refs_json TEXT,
    limitations TEXT,
    uncertainty REAL,
    resource_actuals_json TEXT,
    retry_count INTEGER DEFAULT 0,
    failure_class TEXT,
    downstream_usefulness TEXT,
    policy_version TEXT NOT NULL DEFAULT 'F9.0',
    supersedes_outcome_id TEXT,
    semantic_basis_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_mission_outcome_mission ON mission_outcome(mission_id);
CREATE INDEX IF NOT EXISTS idx_mission_outcome_delegation ON mission_outcome(delegation_id);
CREATE INDEX IF NOT EXISTS idx_mission_outcome_class ON mission_outcome(outcome_class);
CREATE INDEX IF NOT EXISTS idx_mission_outcome_basis_hash ON mission_outcome(mission_id, semantic_basis_hash);

CREATE TABLE IF NOT EXISTS executive_policy_version (
    policy_version_id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    policy_type TEXT NOT NULL,
    effective_from TEXT,
    effective_until TEXT,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    configuration_json TEXT NOT NULL,
    change_reason TEXT,
    evidence_refs_json TEXT,
    provenance_refs_json TEXT,
    created_by TEXT NOT NULL DEFAULT 'nexus_kernel',
    authority_level TEXT NOT NULL DEFAULT 'A1',
    supersedes_version_id TEXT,
    rollback_target_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_policy_version_policy_id ON executive_policy_version(policy_id);
CREATE INDEX IF NOT EXISTS idx_policy_version_status ON executive_policy_version(policy_id, status);
CREATE INDEX IF NOT EXISTS idx_policy_version_type ON executive_policy_version(policy_type);

CREATE TABLE IF NOT EXISTS executive_escalation (
    escalation_id TEXT PRIMARY KEY,
    mission_id TEXT,
    trigger_id TEXT,
    escalation_class TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'MEDIUM',
    created_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    evidence_refs_json TEXT,
    provenance_refs_json TEXT,
    current_policy_version_id TEXT,
    requested_authority TEXT,
    current_authority_ceiling TEXT,
    recommended_options_json TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN',
    resolved_at TEXT,
    resolution_json TEXT,
    resolver TEXT,
    dedup_key TEXT
);
CREATE INDEX IF NOT EXISTS idx_escalation_status ON executive_escalation(status);
CREATE INDEX IF NOT EXISTS idx_escalation_mission ON executive_escalation(mission_id);
CREATE INDEX IF NOT EXISTS idx_escalation_dedup ON executive_escalation(dedup_key, status);

CREATE TABLE IF NOT EXISTS episode_index (
    episode_id TEXT PRIMARY KEY,
    episode_type TEXT NOT NULL,
    root_trigger_id TEXT,
    mission_ids_json TEXT,
    institution_ids_json TEXT,
    start_time TEXT NOT NULL,
    end_time TEXT,
    outcome_ids_json TEXT,
    evidence_refs_json TEXT,
    provenance_refs_json TEXT,
    policy_versions_json TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_episode_trigger ON episode_index(root_trigger_id);
CREATE INDEX IF NOT EXISTS idx_episode_type ON episode_index(episode_type);

CREATE TABLE IF NOT EXISTS semantic_memory (
    semantic_id TEXT PRIMARY KEY,
    statement TEXT NOT NULL,
    claim_class TEXT NOT NULL,
    evidence_refs_json TEXT,
    provenance_refs_json TEXT,
    valid_from TEXT NOT NULL,
    valid_until TEXT,
    confidence_basis TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    supersedes_id TEXT,
    semantic_basis_hash TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_semantic_claim_class ON semantic_memory(claim_class);
CREATE INDEX IF NOT EXISTS idx_semantic_status ON semantic_memory(status);
CREATE INDEX IF NOT EXISTS idx_semantic_basis_hash ON semantic_memory(semantic_basis_hash);

CREATE TABLE IF NOT EXISTS outcome_evaluation_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT NOT NULL,
    semantic_basis_hash TEXT NOT NULL,
    existing_outcome_id TEXT NOT NULL,
    attempted_at TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT 'idempotent re-evaluation attempt, no new semantic outcome created'
);
CREATE INDEX IF NOT EXISTS idx_outcome_audit_mission ON outcome_evaluation_audit_log(mission_id);

CREATE TABLE IF NOT EXISTS learning_event (
    learning_event_id TEXT PRIMARY KEY,
    source_mission_id TEXT NOT NULL,
    observation_type TEXT NOT NULL,
    observed_value REAL,
    expected_value REAL,
    difference REAL,
    evidence_refs_json TEXT,
    confidence_basis TEXT,
    recommended_policy TEXT,
    recommended_change TEXT,
    sample_size INTEGER,
    status TEXT NOT NULL DEFAULT 'OBSERVED',
    created_at TEXT NOT NULL,
    policy_version TEXT NOT NULL DEFAULT 'F9.0'
);
CREATE INDEX IF NOT EXISTS idx_learning_event_mission ON learning_event(source_mission_id);
CREATE INDEX IF NOT EXISTS idx_learning_event_status ON learning_event(status);

CREATE TABLE IF NOT EXISTS policy_proposal (
    proposal_id TEXT PRIMARY KEY,
    target_policy TEXT NOT NULL,
    current_version TEXT NOT NULL,
    evidence_basis TEXT,
    sample_size INTEGER,
    suggested_change TEXT NOT NULL,
    risk TEXT,
    status TEXT NOT NULL DEFAULT 'PROPOSED',
    created_at TEXT NOT NULL,
    policy_version TEXT NOT NULL DEFAULT 'F9.0'
);
CREATE INDEX IF NOT EXISTS idx_policy_proposal_status ON policy_proposal(status);

CREATE TABLE IF NOT EXISTS event_inbox (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    received_at TEXT NOT NULL,
    source_institution TEXT,
    subject TEXT,
    payload_ref TEXT,
    evidence_refs_json TEXT,
    provenance_refs_json TEXT,
    correlation_id TEXT,
    causation_id TEXT,
    dedup_key TEXT NOT NULL,
    policy_context TEXT,
    schema_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'RECEIVED',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error_class TEXT,
    last_error_reason TEXT,
    dead_lettered_at TEXT,
    resulting_delegation_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_event_inbox_status ON event_inbox(status);
CREATE INDEX IF NOT EXISTS idx_event_inbox_dedup ON event_inbox(dedup_key);
CREATE INDEX IF NOT EXISTS idx_event_inbox_correlation ON event_inbox(correlation_id);

CREATE TABLE IF NOT EXISTS loop_observability (
    counter_name TEXT PRIMARY KEY,
    counter_value INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS shadow_decision (
    shadow_decision_id TEXT PRIMARY KEY,
    source_institution TEXT NOT NULL,
    source_cycle_id TEXT,
    semantic_basis_hash TEXT NOT NULL,
    attention_class TEXT,
    attention_score REAL,
    priority_class TEXT,
    priority_score REAL,
    recommended_action TEXT,
    recommended_recipient TEXT,
    authority_required TEXT,
    would_dispatch INTEGER NOT NULL DEFAULT 0,
    authority_would_have_allowed INTEGER,
    blocked_reason TEXT,
    evidence_refs_json TEXT,
    policy_version TEXT NOT NULL DEFAULT 'F9.0',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_shadow_decision_institution ON shadow_decision(source_institution);
CREATE INDEX IF NOT EXISTS idx_shadow_decision_basis_hash ON shadow_decision(source_institution, semantic_basis_hash);
"""


class FederationStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        conn = self._connect()
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ---- institution registry -------------------------------------------

    def get_registry_entry(self, institution_id: str) -> Optional[dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT registry_json FROM institution_registry WHERE institution_id = ?",
                (institution_id,),
            ).fetchone()
            return json.loads(row[0]) if row else None

    def upsert_registry_entry(self, institution_id: str, entry: dict[str, Any], updated_at: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO institution_registry (institution_id, registry_json, updated_at) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(institution_id) DO UPDATE SET registry_json = excluded.registry_json, "
                "updated_at = excluded.updated_at",
                (institution_id, json.dumps(entry), updated_at),
            )

    def all_registry_entries(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute("SELECT registry_json FROM institution_registry").fetchall()
            return [json.loads(r[0]) for r in rows]

    # ---- report log -------------------------------------------------------

    def last_accepted_report(self, institution_id: str) -> Optional[dict[str, Any]]:
        """The most recent report whose `accepted` flag is true, ordered by
        report_timestamp (not insertion order -- a genuinely-accepted
        duplicate/expired/stale report is still the "latest accepted" by
        report content time, not by when NEXUS happened to see it)."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT cycle_id, report_timestamp, report_json FROM report_log "
                "WHERE institution_id = ? AND accepted = 1 "
                "ORDER BY report_timestamp DESC LIMIT 1",
                (institution_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "cycle_id": row[0],
                "report_timestamp": row[1],
                "report": json.loads(row[2]),
            }

    def find_by_cycle(self, institution_id: str, cycle_id: str) -> Optional[dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT report_json, accepted FROM report_log "
                "WHERE institution_id = ? AND cycle_id = ? AND accepted = 1 "
                "ORDER BY id DESC LIMIT 1",
                (institution_id, cycle_id),
            ).fetchone()
            if not row:
                return None
            return {"report": json.loads(row[0]), "accepted": bool(row[1])}

    def append_report_log(
        self,
        *,
        institution_id: str,
        cycle_id: str,
        report_timestamp: str,
        received_at: str,
        temporal_classification: str,
        accepted: bool,
        reason: str,
        report_json: dict[str, Any],
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO report_log "
                "(institution_id, cycle_id, report_timestamp, received_at, "
                " temporal_classification, accepted, reason, report_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    institution_id,
                    cycle_id,
                    report_timestamp,
                    received_at,
                    temporal_classification,
                    1 if accepted else 0,
                    reason,
                    json.dumps(report_json),
                ),
            )

    def commit_accepted_cycle(
        self,
        *,
        report_log_row: dict[str, Any],
        registry_institution_id: str,
        registry_entry: dict[str, Any],
        registry_updated_at: str,
        state_events: list[dict[str, Any]],
    ) -> None:
        """Persist the report_log row, the registry upsert, and every
        state_event row for one accepted, non-duplicate cycle IN ONE
        TRANSACTION (NEXUS Federation F2). This is the crash-safety fix for
        the gap where these were three independent auto-committed writes:
        a crash between them could leave report_log showing a cycle as
        accepted while institution_registry still held the prior state
        forever (a subsequent retry of the same cycle_id would be
        classified DUPLICATE and, correctly, never re-run evidence
        resolution -- silently freezing the registry on stale state). With
        a single transaction, either all three land or none do; a crash
        mid-way leaves the pre-cycle state fully intact, and a retry is
        classified CURRENT (not DUPLICATE), reprocessing the cycle from
        scratch. See PROCESS_RECOVERY_PROTOCOL.md.
        """
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO report_log "
                "(institution_id, cycle_id, report_timestamp, received_at, "
                " temporal_classification, accepted, reason, report_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    report_log_row["institution_id"],
                    report_log_row["cycle_id"],
                    report_log_row["report_timestamp"],
                    report_log_row["received_at"],
                    report_log_row["temporal_classification"],
                    1 if report_log_row["accepted"] else 0,
                    report_log_row["reason"],
                    json.dumps(report_log_row["report_json"]),
                ),
            )
            conn.execute(
                "INSERT INTO institution_registry (institution_id, registry_json, updated_at) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(institution_id) DO UPDATE SET registry_json = excluded.registry_json, "
                "updated_at = excluded.updated_at",
                (registry_institution_id, json.dumps(registry_entry), registry_updated_at),
            )
            for ev in state_events:
                conn.execute(
                    "INSERT INTO state_event_log "
                    "(institution_id, capability_name, cycle_id, prior_lifecycle, new_lifecycle, "
                    " executive_state_class, temporal_classification, transition_reason, "
                    " evidence_refs_json, recorded_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        ev["institution_id"],
                        ev["capability_name"],
                        ev["cycle_id"],
                        ev["prior_lifecycle"],
                        ev["new_lifecycle"],
                        ev["executive_state_class"],
                        ev["temporal_classification"],
                        ev["transition_reason"],
                        json.dumps(ev["evidence_refs"]),
                        ev["recorded_at"],
                    ),
                )

    def count_reports(self, institution_id: str | None = None, **filters: Any) -> int:
        query = "SELECT COUNT(*) FROM report_log WHERE 1=1"
        params: list[Any] = []
        if institution_id:
            query += " AND institution_id = ?"
            params.append(institution_id)
        for col, val in filters.items():
            query += f" AND {col} = ?"
            params.append(val)
        with self.connection() as conn:
            return conn.execute(query, params).fetchone()[0]

    # ---- delegation log ---------------------------------------------------

    def append_delegation(self, proposal: dict[str, Any]) -> bool:
        """Insert a delegation proposal, keyed for idempotency by
        `proposal["idempotency_key"]` (NOT `proposal_id`, which is a random
        UUID generated fresh every call and therefore useless for
        deduplication). Returns True if this call actually inserted a new
        row, False if a delegation with the same idempotency_key already
        existed -- the caller uses this to distinguish "a new delegation
        was created" from "this was correctly suppressed as a duplicate."
        """
        with self.connection() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO delegation_log "
                "(proposal_id, idempotency_key, parent_mission, recipient, created_at, proposal_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    proposal["proposal_id"],
                    proposal["idempotency_key"],
                    proposal["parent_mission"],
                    proposal["recipient"],
                    proposal["created_at"],
                    json.dumps(proposal),
                ),
            )
            return cursor.rowcount == 1

    def get_delegation_by_idempotency_key(self, idempotency_key: str) -> Optional[dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT proposal_json FROM delegation_log WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            return json.loads(row[0]) if row else None

    def count_delegations(self) -> int:
        with self.connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM delegation_log").fetchone()[0]

    def all_delegations(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute("SELECT proposal_json FROM delegation_log ORDER BY id").fetchall()
            return [json.loads(r[0]) for r in rows]

    # ---- evidence baselines ------------------------------------------------

    def get_evidence_baseline(self, institution_id: str, ref: str) -> Optional[str]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT sha256 FROM evidence_baseline WHERE institution_id = ? AND ref = ?",
                (institution_id, ref),
            ).fetchone()
            return row[0] if row else None

    def set_evidence_baseline_if_absent(
        self, institution_id: str, ref: str, sha256: str, first_seen_at: str
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO evidence_baseline (institution_id, ref, sha256, first_seen_at) "
                "VALUES (?, ?, ?, ?)",
                (institution_id, ref, sha256, first_seen_at),
            )

    # ---- evidence resolution ledger (F2) -----------------------------------
    # Append-only: every resolution ATTEMPT gets its own row, forever. A
    # later successful resolution never overwrites an earlier failed one --
    # see EVIDENCE_RESOLUTION_LEDGER_SPEC.md.

    def append_evidence_resolution(
        self,
        *,
        resolution_id: str,
        timestamp: str,
        institution: str,
        mission_id: Optional[str],
        cycle_id: str,
        evidence_ref: str,
        expected_hash: Optional[str],
        observed_hash: Optional[str],
        existence: bool,
        verification_result: str,
        reason: str,
        resolver_version: str,
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO evidence_resolution_ledger "
                "(resolution_id, timestamp, institution, mission_id, cycle_id, evidence_ref, "
                " expected_hash, observed_hash, existence, verification_result, reason, resolver_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    resolution_id,
                    timestamp,
                    institution,
                    mission_id,
                    cycle_id,
                    evidence_ref,
                    expected_hash,
                    observed_hash,
                    1 if existence else 0,
                    verification_result,
                    reason,
                    resolver_version,
                ),
            )

    def get_evidence_resolution_history(self, institution: str, evidence_ref: str) -> list[dict[str, Any]]:
        """Full, ordered history of every resolution attempt for one
        (institution, ref) pair -- oldest first. Never mutated, never
        pruned."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT resolution_id, timestamp, mission_id, cycle_id, expected_hash, "
                "observed_hash, existence, verification_result, reason, resolver_version "
                "FROM evidence_resolution_ledger "
                "WHERE institution = ? AND evidence_ref = ? ORDER BY id ASC",
                (institution, evidence_ref),
            ).fetchall()
            return [
                {
                    "resolution_id": r[0],
                    "timestamp": r[1],
                    "mission_id": r[2],
                    "cycle_id": r[3],
                    "expected_hash": r[4],
                    "observed_hash": r[5],
                    "existence": bool(r[6]),
                    "verification_result": r[7],
                    "reason": r[8],
                    "resolver_version": r[9],
                }
                for r in rows
            ]

    def count_evidence_resolutions(self, **filters: Any) -> int:
        query = "SELECT COUNT(*) FROM evidence_resolution_ledger WHERE 1=1"
        params: list[Any] = []
        for col, val in filters.items():
            query += f" AND {col} = ?"
            params.append(val)
        with self.connection() as conn:
            return conn.execute(query, params).fetchone()[0]

    # ---- provenance records (F2) -------------------------------------------
    # Insert-only. There is deliberately no update_provenance_record method:
    # a provenance record, once written, is immutable for the life of the
    # store -- see PROVENANCE_GRAPH_SPEC.md.

    def append_provenance_record(self, record: dict[str, Any]) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO provenance_record (provenance_id, record_json, ingestion_timestamp) "
                "VALUES (?, ?, ?)",
                (record["provenance_id"], json.dumps(record), record["ingestion_timestamp"]),
            )

    def get_provenance_record(self, provenance_id: str) -> Optional[dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT record_json FROM provenance_record WHERE provenance_id = ?",
                (provenance_id,),
            ).fetchone()
            return json.loads(row[0]) if row else None

    def count_provenance_records(self) -> int:
        with self.connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM provenance_record").fetchone()[0]

    # ---- executive state event history (F2) --------------------------------
    # Append-only, independent of institution_registry's materialized
    # "current state" -- see EXECUTIVE_STATE_EVENT_MODEL.md.

    def append_state_event(
        self,
        *,
        institution_id: str,
        capability_name: str,
        cycle_id: str,
        prior_lifecycle: Optional[str],
        new_lifecycle: str,
        executive_state_class: str,
        temporal_classification: str,
        transition_reason: str,
        evidence_refs: list[str],
        recorded_at: str,
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO state_event_log "
                "(institution_id, capability_name, cycle_id, prior_lifecycle, new_lifecycle, "
                " executive_state_class, temporal_classification, transition_reason, "
                " evidence_refs_json, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    institution_id,
                    capability_name,
                    cycle_id,
                    prior_lifecycle,
                    new_lifecycle,
                    executive_state_class,
                    temporal_classification,
                    transition_reason,
                    json.dumps(evidence_refs),
                    recorded_at,
                ),
            )

    def get_state_events(
        self, institution_id: str, capability_name: Optional[str] = None
    ) -> list[dict[str, Any]]:
        query = (
            "SELECT capability_name, cycle_id, prior_lifecycle, new_lifecycle, "
            "executive_state_class, temporal_classification, transition_reason, "
            "evidence_refs_json, recorded_at FROM state_event_log WHERE institution_id = ?"
        )
        params: list[Any] = [institution_id]
        if capability_name is not None:
            query += " AND capability_name = ?"
            params.append(capability_name)
        query += " ORDER BY id ASC"
        with self.connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                {
                    "capability_name": r[0],
                    "cycle_id": r[1],
                    "prior_lifecycle": r[2],
                    "new_lifecycle": r[3],
                    "executive_state_class": r[4],
                    "temporal_classification": r[5],
                    "transition_reason": r[6],
                    "evidence_refs": json.loads(r[7]),
                    "recorded_at": r[8],
                }
                for r in rows
            ]

    def count_state_events(self, institution_id: Optional[str] = None) -> int:
        query = "SELECT COUNT(*) FROM state_event_log WHERE 1=1"
        params: list[Any] = []
        if institution_id is not None:
            query += " AND institution_id = ?"
            params.append(institution_id)
        with self.connection() as conn:
            return conn.execute(query, params).fetchone()[0]

    # ---- delegation delivery (F3) -------------------------------------------
    # The minimum real delivery transport: a recipient institution polls
    # this SAME persisted store for delegations addressed to it that it
    # has not yet claimed, using the existing delegation_log +
    # delegation_delivery_log tables -- not a direct Python function call
    # into NEXUS's process. Claiming is idempotent (UNIQUE proposal_id):
    # two concurrent/duplicate claim attempts for the same proposal only
    # ever succeed once, restart-safe (nothing but this SQLite file is
    # consulted), and auditable (every claim + completion is a durable row).

    def claim_pending_delegations(self, recipient: str) -> list[dict[str, Any]]:
        """Return every delegation for `recipient` not yet claimed, and
        atomically mark each one claimed (delivered_at set) in the same
        call -- so two processes racing to poll never both claim the same
        proposal_id (the UNIQUE constraint on delegation_delivery_log.
        proposal_id makes the second INSERT fail/ignore)."""
        claimed: list[dict[str, Any]] = []
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT proposal_id, proposal_json FROM delegation_log "
                "WHERE recipient = ? AND proposal_id NOT IN "
                "(SELECT proposal_id FROM delegation_delivery_log)",
                (recipient,),
            ).fetchall()
            for proposal_id, proposal_json in rows:
                delivered_at = datetime.now(timezone.utc).isoformat()
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO delegation_delivery_log "
                    "(proposal_id, recipient, delivered_at) VALUES (?, ?, ?)",
                    (proposal_id, recipient, delivered_at),
                )
                if cursor.rowcount == 1:
                    claimed.append(json.loads(proposal_json))
        return claimed

    def mark_delegation_executed(self, proposal_id: str, result_cycle_id: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE delegation_delivery_log SET executed_at = ?, result_cycle_id = ? "
                "WHERE proposal_id = ?",
                (datetime.now(timezone.utc).isoformat(), result_cycle_id, proposal_id),
            )

    def get_delivery_record(self, proposal_id: str) -> Optional[dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT proposal_id, recipient, delivered_at, executed_at, result_cycle_id "
                "FROM delegation_delivery_log WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "proposal_id": row[0],
                "recipient": row[1],
                "delivered_at": row[2],
                "executed_at": row[3],
                "result_cycle_id": row[4],
            }

    def count_delivered(self, recipient: str | None = None) -> int:
        query = "SELECT COUNT(*) FROM delegation_delivery_log WHERE 1=1"
        params: list[Any] = []
        if recipient:
            query += " AND recipient = ?"
            params.append(recipient)
        with self.connection() as conn:
            return conn.execute(query, params).fetchone()[0]

    # ---- observability events (F2) -----------------------------------------
    # A small, generic, append-only event log for things that are true
    # about the OPERATIONAL HISTORY of this store but not derivable from
    # any other table -- e.g. "a process restart against this file was
    # observed and verified" is a fact about the outside world, not a
    # query over report_log/delegation_log. Recorded explicitly by
    # whichever code actually witnessed the event (a restart-recovery
    # test, a crash-recovery test, the kernel's own duplicate-delegation
    # suppression path) -- never inferred or estimated.

    def append_observability_event(self, event_type: str, detail: str, recorded_at: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO observability_event_log (event_type, detail, recorded_at) VALUES (?, ?, ?)",
                (event_type, detail, recorded_at),
            )

    def count_observability_events(self, event_type: str) -> int:
        with self.connection() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM observability_event_log WHERE event_type = ?",
                (event_type,),
            ).fetchone()[0]

    # ---- checkpoint (for hashing the on-disk file deterministically) -----

    def checkpoint(self) -> None:
        """Force a WAL checkpoint so the main .db file on disk reflects all
        committed writes -- used before hashing the file for the subprocess
        restart evidence (FEDERATION_PROCESS_RECOVERY_EVIDENCE.md), so the
        hash is not sensitive to whether WAL pages have been flushed yet."""
        with self.connection() as conn:
            conn.execute("PRAGMA wal_checkpoint(FULL)")

    # ---- Convenience methods for F4C three-process test ----

    def record_delegation_proposal(
        self, delegation_id: str, mission_id: str, target_institution: str, payload: dict[str, Any]
    ) -> None:
        """Record a delegation proposal in the delegation_log.

        Used by Process A (NEXUS delegation creator) to persist the delegation
        for later claiming by Process B.
        """
        idempotency_key = f"{mission_id}:{delegation_id}"
        with self.connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO delegation_log "
                "(proposal_id, idempotency_key, parent_mission, recipient, created_at, proposal_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    delegation_id,
                    idempotency_key,
                    mission_id,
                    target_institution,
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(payload),
                ),
            )

    def claim_delegation(
        self, delegation_id: str, claim_id: str, claimed_by: str, claimed_at: str
    ) -> bool:
        """Mark a delegation as claimed by an institution.

        Used by Process B (Librarian researcher) to claim the persisted
        delegation for execution. Records the claim atomically.
        """
        with self.connection() as conn:
            # Mark as delivered/claimed in delegation_delivery_log
            cursor = conn.execute(
                "INSERT OR IGNORE INTO delegation_delivery_log "
                "(proposal_id, recipient, delivered_at) VALUES (?, ?, ?)",
                (delegation_id, claimed_by, claimed_at),
            )
            return cursor.rowcount == 1

    def log_institutional_report(
        self, institution_id: str, mission_id: str, report_id: str, payload: dict[str, Any]
    ) -> None:
        """Log an institutional report in the report_log.

        Used by Process B (Librarian researcher) to persist the result of
        research execution for later ingestion by Process C.
        """
        with self.connection() as conn:
            now = datetime.now(timezone.utc)
            conn.execute(
                "INSERT INTO report_log "
                "(institution_id, cycle_id, report_timestamp, received_at, temporal_classification, accepted, reason, report_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    institution_id,
                    report_id,
                    now.isoformat(),
                    now.isoformat(),
                    "UNCLASSIFIED",
                    0,  # Not yet accepted by kernel
                    "Persisted by researcher process",
                    json.dumps(payload),
                ),
            )

    def get_institutional_report(self, report_id: str) -> Optional[dict[str, Any]]:
        """Retrieve a persisted institutional report by ID.

        Used by Process C (NEXUS ingester) to discover and ingest the
        Librarian's report from the federation store.
        """
        with self.connection() as conn:
            row = conn.execute(
                "SELECT report_json FROM report_log WHERE cycle_id = ? LIMIT 1",
                (report_id,),
            ).fetchone()
            if not row:
                return None
            return json.loads(row[0])

    def commit(self) -> None:
        """Explicitly commit current transaction.

        Used by subprocess helpers to ensure persistence before exiting.
        """
        with self.connection() as conn:
            conn.commit()

    # ---- mission lifecycle (F9) ----

    def record_mission_transition(
        self,
        event_id: str,
        delegation_id: str,
        previous_state: Optional[str],
        new_state: str,
        reason: str,
        actor: str = "nexus",
        policy_version: str = "F9.0",
        evidence_refs: Optional[list[str]] = None,
        provenance_refs: Optional[list[str]] = None,
        lease_id: Optional[str] = None,
        retry_count: Optional[int] = None,
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record a mission lifecycle state transition (append-only).

        Args:
            event_id: unique identifier for this event
            delegation_id: canonical delegation this mission is based on
            previous_state: prior state (None if PROPOSED)
            new_state: target state (PROPOSED/VALIDATED/QUEUED/CLAIMED/RUNNING/etc)
            reason: human-readable reason for transition
            actor: who triggered this (nexus, scheduler, human, etc)
            policy_version: versioned policy in effect
            evidence_refs: optional references to supporting evidence
            provenance_refs: optional provenance chain ids
            lease_id: optional lease id if claimed
            retry_count: optional retry attempt number
            detail: optional dict with extra context
        """
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO mission_lifecycle_event "
                "(event_id, delegation_id, previous_state, new_state, timestamp, actor, "
                "reason, policy_version, evidence_refs_json, provenance_refs_json, "
                "lease_id, retry_count, detail_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    delegation_id,
                    previous_state,
                    new_state,
                    datetime.now(timezone.utc).isoformat(),
                    actor,
                    reason,
                    policy_version,
                    json.dumps(evidence_refs) if evidence_refs else None,
                    json.dumps(provenance_refs) if provenance_refs else None,
                    lease_id,
                    retry_count,
                    json.dumps(detail) if detail else None,
                ),
            )

    def get_mission_state(self, delegation_id: str) -> Optional[str]:
        """Get the current state of a mission (from most recent event)."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT new_state FROM mission_lifecycle_event "
                "WHERE delegation_id = ? "
                "ORDER BY timestamp DESC LIMIT 1",
                (delegation_id,),
            ).fetchone()
            return row[0] if row else None

    def get_mission_history(self, delegation_id: str) -> list[dict[str, Any]]:
        """Get full lifecycle history for a mission (newest first)."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT event_id, delegation_id, previous_state, new_state, timestamp, "
                "actor, reason, policy_version, evidence_refs_json, provenance_refs_json, "
                "lease_id, retry_count, detail_json "
                "FROM mission_lifecycle_event "
                "WHERE delegation_id = ? "
                "ORDER BY timestamp DESC",
                (delegation_id,),
            ).fetchall()
            return [
                {
                    "event_id": r[0],
                    "delegation_id": r[1],
                    "previous_state": r[2],
                    "new_state": r[3],
                    "timestamp": r[4],
                    "actor": r[5],
                    "reason": r[6],
                    "policy_version": r[7],
                    "evidence_refs": json.loads(r[8]) if r[8] else [],
                    "provenance_refs": json.loads(r[9]) if r[9] else [],
                    "lease_id": r[10],
                    "retry_count": r[11],
                    "detail": json.loads(r[12]) if r[12] else {},
                }
                for r in rows
            ]

    def list_missions_by_state(self, state: str) -> list[str]:
        """List all delegation_ids currently in a given state."""
        with self.connection() as conn:
            # Get most recent state per delegation
            rows = conn.execute(
                "SELECT DISTINCT delegation_id FROM mission_lifecycle_event "
                "WHERE new_state = ? AND timestamp = ("
                "  SELECT MAX(timestamp) FROM mission_lifecycle_event m2 "
                "  WHERE m2.delegation_id = mission_lifecycle_event.delegation_id"
                ")",
                (state,),
            ).fetchall()
            return [r[0] for r in rows]

    # ---- mission dependencies (F9 Phase C) ----

    def record_dependency(
        self,
        dependency_id: str,
        mission_id: str,
        depends_on_mission_id: str,
        dependency_type: str,
        reason: str,
        policy_version: str = "F9.0",
        evidence_refs: Optional[list[str]] = None,
        provenance_refs: Optional[list[str]] = None,
    ) -> None:
        """Record a mission dependency (append-only)."""
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO mission_dependency "
                "(dependency_id, mission_id, depends_on_mission_id, dependency_type, "
                "created_at, reason, policy_version, evidence_refs_json, provenance_refs_json, active) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                (
                    dependency_id,
                    mission_id,
                    depends_on_mission_id,
                    dependency_type,
                    datetime.now(timezone.utc).isoformat(),
                    reason,
                    policy_version,
                    json.dumps(evidence_refs) if evidence_refs else None,
                    json.dumps(provenance_refs) if provenance_refs else None,
                ),
            )

    def get_mission_dependencies(self, mission_id: str) -> list[dict[str, Any]]:
        """Get all active dependencies for a mission."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT dependency_id, mission_id, depends_on_mission_id, dependency_type, "
                "created_at, reason, policy_version, evidence_refs_json, provenance_refs_json "
                "FROM mission_dependency "
                "WHERE mission_id = ? AND active = 1 "
                "ORDER BY created_at",
                (mission_id,),
            ).fetchall()
            return [
                {
                    "dependency_id": r[0],
                    "mission_id": r[1],
                    "depends_on_mission_id": r[2],
                    "dependency_type": r[3],
                    "created_at": r[4],
                    "reason": r[5],
                    "policy_version": r[6],
                    "evidence_refs": json.loads(r[7]) if r[7] else [],
                    "provenance_refs": json.loads(r[8]) if r[8] else [],
                }
                for r in rows
            ]

    def get_mission_prerequisites(self, mission_id: str) -> list[str]:
        """Get all missions this mission depends on."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT depends_on_mission_id FROM mission_dependency "
                "WHERE mission_id = ? AND active = 1",
                (mission_id,),
            ).fetchall()
            return [r[0] for r in rows]

    def deactivate_dependency(self, dependency_id: str) -> None:
        """Deactivate a dependency (soft delete)."""
        with self.connection() as conn:
            conn.execute(
                "UPDATE mission_dependency SET active = 0 WHERE dependency_id = ?",
                (dependency_id,),
            )

    # ---- institution capacity (F9 Phase D) ----

    def get_institution_capacity(self, institution_id: str) -> Optional[dict[str, Any]]:
        """Get capacity state for an institution."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT availability_state, max_concurrent_missions, active_missions, "
                "queued_missions, cpu_pressure_percent, memory_pressure_percent, "
                "storage_pressure_percent, api_pressure_percent, circuit_state, "
                "last_heartbeat, last_successful_cycle, updated_at, policy_version "
                "FROM institution_capacity WHERE institution_id = ?",
                (institution_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "institution_id": institution_id,
                "availability_state": row[0],
                "max_concurrent_missions": row[1],
                "active_missions": row[2],
                "queued_missions": row[3],
                "cpu_pressure_percent": row[4],
                "memory_pressure_percent": row[5],
                "storage_pressure_percent": row[6],
                "api_pressure_percent": row[7],
                "circuit_state": row[8],
                "last_heartbeat": row[9],
                "last_successful_cycle": row[10],
                "updated_at": row[11],
                "policy_version": row[12],
            }

    def upsert_institution_capacity(
        self, institution_id: str, capacity: dict[str, Any]
    ) -> None:
        """Update or insert institution capacity state."""
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO institution_capacity "
                "(institution_id, availability_state, max_concurrent_missions, "
                "active_missions, queued_missions, circuit_state, updated_at, policy_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(institution_id) DO UPDATE SET "
                "availability_state = excluded.availability_state, "
                "max_concurrent_missions = excluded.max_concurrent_missions, "
                "active_missions = excluded.active_missions, "
                "queued_missions = excluded.queued_missions, "
                "circuit_state = excluded.circuit_state, "
                "updated_at = excluded.updated_at, "
                "policy_version = excluded.policy_version",
                (
                    institution_id,
                    capacity.get("availability_state", "UNKNOWN"),
                    capacity.get("max_concurrent_missions", 5),
                    capacity.get("active_missions", 0),
                    capacity.get("queued_missions", 0),
                    capacity.get("circuit_state", "CLOSED"),
                    datetime.now(timezone.utc).isoformat(),
                    capacity.get("policy_version", "F9.0"),
                ),
            )

    # ---- mission outcomes (F9 Phase E) ----

    @staticmethod
    def compute_outcome_semantic_basis_hash(outcome_dict: dict[str, Any]) -> str:
        """Semantic idempotency key: same mission + evidence + criteria +
        policy version + basis => same hash => no duplicate semantic outcome.

        Deliberately excludes: outcome_id, evaluated_at, outcome_class,
        supersedes_outcome_id -- a re-evaluation with the SAME inputs producing
        a DIFFERENT class is still a duplicate semantic attempt (the class is
        an output, not part of the basis) and is logged to the audit trail,
        not inserted as a new mission_outcome row.
        """
        import hashlib

        basis = {
            "mission_id": outcome_dict.get("mission_id"),
            "evidence_refs": sorted(outcome_dict.get("evidence_refs") or []),
            "success_criteria": sorted(outcome_dict.get("success_criteria") or []),
            "policy_version": outcome_dict.get("policy_version", "F9.0"),
            "objective": outcome_dict.get("objective"),
        }
        canonical = json.dumps(basis, sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def find_outcome_by_basis_hash(self, mission_id: str, semantic_basis_hash: str) -> Optional[str]:
        """Return existing outcome_id for this exact semantic basis, if any."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT outcome_id FROM mission_outcome "
                "WHERE mission_id = ? AND semantic_basis_hash = ? "
                "ORDER BY evaluated_at ASC LIMIT 1",
                (mission_id, semantic_basis_hash),
            ).fetchone()
            return row[0] if row else None

    def record_outcome_audit_attempt(
        self, mission_id: str, semantic_basis_hash: str, existing_outcome_id: str
    ) -> None:
        """Log a re-evaluation attempt that matched an existing semantic outcome."""
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO outcome_evaluation_audit_log "
                "(mission_id, semantic_basis_hash, existing_outcome_id, attempted_at) "
                "VALUES (?, ?, ?, ?)",
                (mission_id, semantic_basis_hash, existing_outcome_id, datetime.now(timezone.utc).isoformat()),
            )

    def get_outcome_audit_log(self, mission_id: str) -> list[dict[str, Any]]:
        """Get all audit-logged re-evaluation attempts for a mission."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT mission_id, semantic_basis_hash, existing_outcome_id, attempted_at, reason "
                "FROM outcome_evaluation_audit_log WHERE mission_id = ? ORDER BY attempted_at ASC",
                (mission_id,),
            ).fetchall()
            return [
                {
                    "mission_id": r[0],
                    "semantic_basis_hash": r[1],
                    "existing_outcome_id": r[2],
                    "attempted_at": r[3],
                    "reason": r[4],
                }
                for r in rows
            ]

    def record_outcome(self, outcome_dict: dict[str, Any], enforce_idempotency: bool = True) -> tuple[str, bool]:
        """Record mission outcome (append-only, versioned).

        Semantic idempotency: same mission + evidence + success_criteria +
        policy_version + objective => same semantic_basis_hash => the
        re-evaluation is logged to outcome_evaluation_audit_log and the
        EXISTING outcome_id is returned; no duplicate mission_outcome row
        is inserted.

        Returns (outcome_id, created) -- created=False means an existing
        semantic outcome was matched and this call was audit-logged instead.
        """
        basis_hash = self.compute_outcome_semantic_basis_hash(outcome_dict)

        if enforce_idempotency:
            existing_id = self.find_outcome_by_basis_hash(outcome_dict.get("mission_id"), basis_hash)
            if existing_id:
                self.record_outcome_audit_attempt(outcome_dict.get("mission_id"), basis_hash, existing_id)
                return existing_id, False

        with self.connection() as conn:
            conn.execute(
                "INSERT INTO mission_outcome "
                "(outcome_id, mission_id, delegation_id, outcome_class, evaluated_at, "
                "evaluator, objective, success_criteria_json, criteria_met_json, "
                "criteria_unmet_json, evidence_refs_json, provenance_refs_json, "
                "limitations, uncertainty, resource_actuals_json, retry_count, "
                "failure_class, downstream_usefulness, policy_version, supersedes_outcome_id, "
                "semantic_basis_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    outcome_dict.get("outcome_id"),
                    outcome_dict.get("mission_id"),
                    outcome_dict.get("delegation_id"),
                    outcome_dict.get("outcome_class"),
                    outcome_dict.get("evaluated_at", datetime.now(timezone.utc).isoformat()),
                    outcome_dict.get("evaluator", "nexus_kernel"),
                    outcome_dict.get("objective"),
                    json.dumps(outcome_dict.get("success_criteria", [])) if outcome_dict.get("success_criteria") else None,
                    json.dumps(outcome_dict.get("criteria_met", [])) if outcome_dict.get("criteria_met") else None,
                    json.dumps(outcome_dict.get("criteria_unmet", [])) if outcome_dict.get("criteria_unmet") else None,
                    json.dumps(outcome_dict.get("evidence_refs", [])) if outcome_dict.get("evidence_refs") else None,
                    json.dumps(outcome_dict.get("provenance_refs", [])) if outcome_dict.get("provenance_refs") else None,
                    outcome_dict.get("limitations"),
                    outcome_dict.get("uncertainty"),
                    json.dumps(outcome_dict.get("resource_actuals", {})) if outcome_dict.get("resource_actuals") else None,
                    outcome_dict.get("retry_count", 0),
                    outcome_dict.get("failure_class"),
                    outcome_dict.get("downstream_usefulness"),
                    outcome_dict.get("policy_version", "F9.0"),
                    outcome_dict.get("supersedes_outcome_id"),
                    basis_hash,
                ),
            )
        return outcome_dict.get("outcome_id"), True

    def get_mission_outcomes(self, mission_id: str) -> list[dict[str, Any]]:
        """Get all outcome records for a mission (newest first)."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT outcome_id, mission_id, delegation_id, outcome_class, evaluated_at, "
                "objective, criteria_met_json, criteria_unmet_json, evidence_refs_json, "
                "failure_class, downstream_usefulness "
                "FROM mission_outcome WHERE mission_id = ? ORDER BY evaluated_at DESC",
                (mission_id,),
            ).fetchall()
            return [
                {
                    "outcome_id": r[0],
                    "mission_id": r[1],
                    "delegation_id": r[2],
                    "outcome_class": r[3],
                    "evaluated_at": r[4],
                    "objective": r[5],
                    "criteria_met": json.loads(r[6]) if r[6] else [],
                    "criteria_unmet": json.loads(r[7]) if r[7] else [],
                    "evidence_refs": json.loads(r[8]) if r[8] else [],
                    "failure_class": r[9],
                    "downstream_usefulness": r[10],
                }
                for r in rows
            ]

    # ---- learning events (F9 Phase E) ----

    def record_learning_event(self, event_dict: dict[str, Any]) -> None:
        """Record a learning observation (bounded learning, sample-size guarded)."""
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO learning_event "
                "(learning_event_id, source_mission_id, observation_type, observed_value, "
                "expected_value, difference, evidence_refs_json, confidence_basis, "
                "recommended_policy, recommended_change, sample_size, status, created_at, policy_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_dict.get("learning_event_id"),
                    event_dict.get("source_mission_id"),
                    event_dict.get("observation_type"),
                    event_dict.get("observed_value"),
                    event_dict.get("expected_value"),
                    event_dict.get("difference"),
                    json.dumps(event_dict.get("evidence_refs", [])) if event_dict.get("evidence_refs") else None,
                    event_dict.get("confidence_basis"),
                    event_dict.get("recommended_policy"),
                    event_dict.get("recommended_change"),
                    event_dict.get("sample_size"),
                    event_dict.get("status", "OBSERVED"),
                    event_dict.get("created_at", datetime.now(timezone.utc).isoformat()),
                    event_dict.get("policy_version", "F9.0"),
                ),
            )

    def get_learning_events(self, source_mission_id: str) -> list[dict[str, Any]]:
        """Get all learning events for a mission."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT learning_event_id, source_mission_id, observation_type, observed_value, "
                "expected_value, difference, evidence_refs_json, sample_size, status "
                "FROM learning_event WHERE source_mission_id = ? ORDER BY created_at DESC",
                (source_mission_id,),
            ).fetchall()
            return [
                {
                    "learning_event_id": r[0],
                    "source_mission_id": r[1],
                    "observation_type": r[2],
                    "observed_value": r[3],
                    "expected_value": r[4],
                    "difference": r[5],
                    "evidence_refs": json.loads(r[6]) if r[6] else [],
                    "sample_size": r[7],
                    "status": r[8],
                }
                for r in rows
            ]

    def record_policy_proposal(self, proposal_dict: dict[str, Any]) -> None:
        """Record a policy change proposal (proposed, not auto-activated)."""
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO policy_proposal "
                "(proposal_id, target_policy, current_version, evidence_basis, "
                "sample_size, suggested_change, risk, status, created_at, policy_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    proposal_dict.get("proposal_id"),
                    proposal_dict.get("target_policy"),
                    proposal_dict.get("current_version"),
                    proposal_dict.get("evidence_basis"),
                    proposal_dict.get("sample_size"),
                    proposal_dict.get("suggested_change"),
                    proposal_dict.get("risk"),
                    proposal_dict.get("status", "PROPOSED"),
                    proposal_dict.get("created_at", datetime.now(timezone.utc).isoformat()),
                    proposal_dict.get("policy_version", "F9.0"),
                ),
            )

    def get_policy_proposals(self, status: Optional[str] = None) -> list[dict[str, Any]]:
        """Get policy proposals, optionally filtered by status."""
        with self.connection() as conn:
            if status:
                rows = conn.execute(
                    "SELECT proposal_id, target_policy, sample_size, suggested_change, risk, status, created_at "
                    "FROM policy_proposal WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT proposal_id, target_policy, sample_size, suggested_change, risk, status, created_at "
                    "FROM policy_proposal ORDER BY created_at DESC",
                ).fetchall()
            return [
                {
                    "proposal_id": r[0],
                    "target_policy": r[1],
                    "sample_size": r[2],
                    "suggested_change": r[3],
                    "risk": r[4],
                    "status": r[5],
                    "created_at": r[6],
                }
                for r in rows
            ]

    # ---- executive policy versioning (F9 Phase G) ----

    def record_policy_version(self, policy_dict: dict[str, Any]) -> None:
        """Persist a new policy version row (append-only)."""
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO executive_policy_version "
                "(policy_version_id, policy_id, version, policy_type, effective_from, "
                "effective_until, status, configuration_json, change_reason, "
                "evidence_refs_json, provenance_refs_json, created_by, authority_level, "
                "supersedes_version_id, rollback_target_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    policy_dict.get("policy_version_id"),
                    policy_dict.get("policy_id"),
                    policy_dict.get("version"),
                    policy_dict.get("policy_type"),
                    policy_dict.get("effective_from"),
                    policy_dict.get("effective_until"),
                    policy_dict.get("status", "DRAFT"),
                    json.dumps(policy_dict.get("configuration", {})),
                    policy_dict.get("change_reason"),
                    json.dumps(policy_dict.get("evidence_refs", [])) if policy_dict.get("evidence_refs") else None,
                    json.dumps(policy_dict.get("provenance_refs", [])) if policy_dict.get("provenance_refs") else None,
                    policy_dict.get("created_by", "nexus_kernel"),
                    policy_dict.get("authority_level", "A1"),
                    policy_dict.get("supersedes_version_id"),
                    policy_dict.get("rollback_target_id"),
                    policy_dict.get("created_at", datetime.now(timezone.utc).isoformat()),
                ),
            )

    def update_policy_version_status(
        self, policy_version_id: str, status: str, effective_until: Optional[str] = None
    ) -> None:
        """Update a policy version's status (e.g. ACTIVE -> SUPERSEDED). No row deletion."""
        with self.connection() as conn:
            if effective_until:
                conn.execute(
                    "UPDATE executive_policy_version SET status = ?, effective_until = ? "
                    "WHERE policy_version_id = ?",
                    (status, effective_until, policy_version_id),
                )
            else:
                conn.execute(
                    "UPDATE executive_policy_version SET status = ? WHERE policy_version_id = ?",
                    (status, policy_version_id),
                )

    def get_policy_version(self, policy_version_id: str) -> Optional[dict[str, Any]]:
        """Get a specific policy version by its ID."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT policy_version_id, policy_id, version, policy_type, effective_from, "
                "effective_until, status, configuration_json, change_reason, "
                "evidence_refs_json, provenance_refs_json, created_by, authority_level, "
                "supersedes_version_id, rollback_target_id, created_at "
                "FROM executive_policy_version WHERE policy_version_id = ?",
                (policy_version_id,),
            ).fetchone()
            if not row:
                return None
            return self._policy_version_row_to_dict(row)

    def get_active_policy_version(self, policy_id: str, at_timestamp: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Resolve the ACTIVE policy version for policy_id at a given timestamp.

        If at_timestamp is None, resolves the currently ACTIVE version.
        If provided, resolves whichever version was ACTIVE (by effective_from/
        effective_until window) at that historical instant -- so historical
        decisions can be re-attributed to the policy that was actually in
        force at the time, never reinterpreted under the current version.
        """
        with self.connection() as conn:
            if at_timestamp is None:
                row = conn.execute(
                    "SELECT policy_version_id, policy_id, version, policy_type, effective_from, "
                    "effective_until, status, configuration_json, change_reason, "
                    "evidence_refs_json, provenance_refs_json, created_by, authority_level, "
                    "supersedes_version_id, rollback_target_id, created_at "
                    "FROM executive_policy_version WHERE policy_id = ? AND status = 'ACTIVE' "
                    "ORDER BY version DESC LIMIT 1",
                    (policy_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT policy_version_id, policy_id, version, policy_type, effective_from, "
                    "effective_until, status, configuration_json, change_reason, "
                    "evidence_refs_json, provenance_refs_json, created_by, authority_level, "
                    "supersedes_version_id, rollback_target_id, created_at "
                    "FROM executive_policy_version WHERE policy_id = ? "
                    "AND effective_from <= ? "
                    "AND (effective_until IS NULL OR effective_until > ?) "
                    "ORDER BY version DESC LIMIT 1",
                    (policy_id, at_timestamp, at_timestamp),
                ).fetchone()
            if not row:
                return None
            return self._policy_version_row_to_dict(row)

    def get_policy_version_history(self, policy_id: str) -> list[dict[str, Any]]:
        """Get all versions of a policy_id, newest first."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT policy_version_id, policy_id, version, policy_type, effective_from, "
                "effective_until, status, configuration_json, change_reason, "
                "evidence_refs_json, provenance_refs_json, created_by, authority_level, "
                "supersedes_version_id, rollback_target_id, created_at "
                "FROM executive_policy_version WHERE policy_id = ? ORDER BY version DESC",
                (policy_id,),
            ).fetchall()
            return [self._policy_version_row_to_dict(r) for r in rows]

    @staticmethod
    def _policy_version_row_to_dict(r) -> dict[str, Any]:
        return {
            "policy_version_id": r[0],
            "policy_id": r[1],
            "version": r[2],
            "policy_type": r[3],
            "effective_from": r[4],
            "effective_until": r[5],
            "status": r[6],
            "configuration": json.loads(r[7]) if r[7] else {},
            "change_reason": r[8],
            "evidence_refs": json.loads(r[9]) if r[9] else [],
            "provenance_refs": json.loads(r[10]) if r[10] else [],
            "created_by": r[11],
            "authority_level": r[12],
            "supersedes_version_id": r[13],
            "rollback_target_id": r[14],
            "created_at": r[15],
        }

    # ---- executive escalation (F9 Phase G) ----

    def record_escalation(self, escalation_dict: dict[str, Any]) -> None:
        """Persist a new escalation (append-only creation; status mutated in place)."""
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO executive_escalation "
                "(escalation_id, mission_id, trigger_id, escalation_class, severity, "
                "created_at, reason, evidence_refs_json, provenance_refs_json, "
                "current_policy_version_id, requested_authority, current_authority_ceiling, "
                "recommended_options_json, status, dedup_key) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    escalation_dict.get("escalation_id"),
                    escalation_dict.get("mission_id"),
                    escalation_dict.get("trigger_id"),
                    escalation_dict.get("escalation_class"),
                    escalation_dict.get("severity", "MEDIUM"),
                    escalation_dict.get("created_at", datetime.now(timezone.utc).isoformat()),
                    escalation_dict.get("reason"),
                    json.dumps(escalation_dict.get("evidence_refs", [])) if escalation_dict.get("evidence_refs") else None,
                    json.dumps(escalation_dict.get("provenance_refs", [])) if escalation_dict.get("provenance_refs") else None,
                    escalation_dict.get("current_policy_version_id"),
                    escalation_dict.get("requested_authority"),
                    escalation_dict.get("current_authority_ceiling"),
                    json.dumps(escalation_dict.get("recommended_options", [])) if escalation_dict.get("recommended_options") else None,
                    escalation_dict.get("status", "OPEN"),
                    escalation_dict.get("dedup_key"),
                ),
            )

    def find_open_escalation_by_dedup_key(self, dedup_key: str) -> Optional[dict[str, Any]]:
        """Find an existing OPEN/ACKNOWLEDGED escalation with the same dedup_key."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT escalation_id, mission_id, escalation_class, severity, status, created_at "
                "FROM executive_escalation "
                "WHERE dedup_key = ? AND status IN ('OPEN', 'ACKNOWLEDGED') "
                "ORDER BY created_at DESC LIMIT 1",
                (dedup_key,),
            ).fetchone()
            if not row:
                return None
            return {
                "escalation_id": row[0],
                "mission_id": row[1],
                "escalation_class": row[2],
                "severity": row[3],
                "status": row[4],
                "created_at": row[5],
            }

    def resolve_escalation(
        self, escalation_id: str, status: str, resolution: dict[str, Any], resolver: str
    ) -> None:
        """Resolve/close an escalation (status update in place, resolution recorded)."""
        with self.connection() as conn:
            conn.execute(
                "UPDATE executive_escalation SET status = ?, resolved_at = ?, "
                "resolution_json = ?, resolver = ? WHERE escalation_id = ?",
                (
                    status,
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(resolution),
                    resolver,
                    escalation_id,
                ),
            )

    def get_escalation(self, escalation_id: str) -> Optional[dict[str, Any]]:
        """Get a single escalation by ID."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT escalation_id, mission_id, trigger_id, escalation_class, severity, "
                "created_at, reason, evidence_refs_json, provenance_refs_json, "
                "current_policy_version_id, requested_authority, current_authority_ceiling, "
                "recommended_options_json, status, resolved_at, resolution_json, resolver, dedup_key "
                "FROM executive_escalation WHERE escalation_id = ?",
                (escalation_id,),
            ).fetchone()
            if not row:
                return None
            return self._escalation_row_to_dict(row)

    def list_escalations(self, status: Optional[str] = None) -> list[dict[str, Any]]:
        """List escalations, optionally filtered by status."""
        with self.connection() as conn:
            if status:
                rows = conn.execute(
                    "SELECT escalation_id, mission_id, trigger_id, escalation_class, severity, "
                    "created_at, reason, evidence_refs_json, provenance_refs_json, "
                    "current_policy_version_id, requested_authority, current_authority_ceiling, "
                    "recommended_options_json, status, resolved_at, resolution_json, resolver, dedup_key "
                    "FROM executive_escalation WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT escalation_id, mission_id, trigger_id, escalation_class, severity, "
                    "created_at, reason, evidence_refs_json, provenance_refs_json, "
                    "current_policy_version_id, requested_authority, current_authority_ceiling, "
                    "recommended_options_json, status, resolved_at, resolution_json, resolver, dedup_key "
                    "FROM executive_escalation ORDER BY created_at DESC",
                ).fetchall()
            return [self._escalation_row_to_dict(r) for r in rows]

    @staticmethod
    def _escalation_row_to_dict(r) -> dict[str, Any]:
        return {
            "escalation_id": r[0],
            "mission_id": r[1],
            "trigger_id": r[2],
            "escalation_class": r[3],
            "severity": r[4],
            "created_at": r[5],
            "reason": r[6],
            "evidence_refs": json.loads(r[7]) if r[7] else [],
            "provenance_refs": json.loads(r[8]) if r[8] else [],
            "current_policy_version_id": r[9],
            "requested_authority": r[10],
            "current_authority_ceiling": r[11],
            "recommended_options": json.loads(r[12]) if r[12] else [],
            "status": r[13],
            "resolved_at": r[14],
            "resolution": json.loads(r[15]) if r[15] else None,
            "resolver": r[16],
            "dedup_key": r[17],
        }

    # ---- executive memory: episodic index (F9 Phase H) ----

    def record_episode(self, episode_dict: dict[str, Any]) -> None:
        """Persist an episode index row. This is an INDEX over canonical
        records (mission_lifecycle_event, mission_outcome, etc.), NOT a
        replacement source of truth -- the linked ids are the only content;
        full record bodies are always re-fetched from their canonical tables.
        """
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO episode_index "
                "(episode_id, episode_type, root_trigger_id, mission_ids_json, "
                "institution_ids_json, start_time, end_time, outcome_ids_json, "
                "evidence_refs_json, provenance_refs_json, policy_versions_json, "
                "status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    episode_dict.get("episode_id"),
                    episode_dict.get("episode_type"),
                    episode_dict.get("root_trigger_id"),
                    json.dumps(episode_dict.get("mission_ids", [])),
                    json.dumps(episode_dict.get("institution_ids", [])),
                    episode_dict.get("start_time", datetime.now(timezone.utc).isoformat()),
                    episode_dict.get("end_time"),
                    json.dumps(episode_dict.get("outcome_ids", [])),
                    json.dumps(episode_dict.get("evidence_refs", [])),
                    json.dumps(episode_dict.get("provenance_refs", [])),
                    json.dumps(episode_dict.get("policy_versions", [])),
                    episode_dict.get("status", "OPEN"),
                    episode_dict.get("created_at", datetime.now(timezone.utc).isoformat()),
                ),
            )

    def update_episode(self, episode_id: str, **fields) -> None:
        """Update mutable episode fields (end_time, status, and *_ids lists
        that grow as the episode progresses)."""
        allowed = {
            "end_time", "status", "mission_ids", "institution_ids",
            "outcome_ids", "evidence_refs", "provenance_refs", "policy_versions",
        }
        json_fields = {"mission_ids", "institution_ids", "outcome_ids", "evidence_refs", "provenance_refs", "policy_versions"}
        set_clauses = []
        values = []
        for k, v in fields.items():
            if k not in allowed:
                continue
            column = f"{k}_json" if k in json_fields else k
            set_clauses.append(f"{column} = ?")
            values.append(json.dumps(v) if k in json_fields else v)
        if not set_clauses:
            return
        values.append(episode_id)
        with self.connection() as conn:
            conn.execute(
                f"UPDATE episode_index SET {', '.join(set_clauses)} WHERE episode_id = ?",
                values,
            )

    def get_episode(self, episode_id: str) -> Optional[dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT episode_id, episode_type, root_trigger_id, mission_ids_json, "
                "institution_ids_json, start_time, end_time, outcome_ids_json, "
                "evidence_refs_json, provenance_refs_json, policy_versions_json, "
                "status, created_at FROM episode_index WHERE episode_id = ?",
                (episode_id,),
            ).fetchone()
            if not row:
                return None
            return self._episode_row_to_dict(row)

    def find_episodes_by_trigger(self, root_trigger_id: str) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT episode_id, episode_type, root_trigger_id, mission_ids_json, "
                "institution_ids_json, start_time, end_time, outcome_ids_json, "
                "evidence_refs_json, provenance_refs_json, policy_versions_json, "
                "status, created_at FROM episode_index WHERE root_trigger_id = ? "
                "ORDER BY start_time DESC",
                (root_trigger_id,),
            ).fetchall()
            return [self._episode_row_to_dict(r) for r in rows]

    def find_episodes_by_mission(self, mission_id: str) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT episode_id, episode_type, root_trigger_id, mission_ids_json, "
                "institution_ids_json, start_time, end_time, outcome_ids_json, "
                "evidence_refs_json, provenance_refs_json, policy_versions_json, "
                "status, created_at FROM episode_index "
                "WHERE mission_ids_json LIKE ? ORDER BY start_time DESC",
                (f'%"{mission_id}"%',),
            ).fetchall()
            return [self._episode_row_to_dict(r) for r in rows]

    def find_episodes_by_institution(self, institution_id: str) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT episode_id, episode_type, root_trigger_id, mission_ids_json, "
                "institution_ids_json, start_time, end_time, outcome_ids_json, "
                "evidence_refs_json, provenance_refs_json, policy_versions_json, "
                "status, created_at FROM episode_index "
                "WHERE institution_ids_json LIKE ? ORDER BY start_time DESC",
                (f'%"{institution_id}"%',),
            ).fetchall()
            return [self._episode_row_to_dict(r) for r in rows]

    def find_episodes_by_outcome(self, outcome_id: str) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT episode_id, episode_type, root_trigger_id, mission_ids_json, "
                "institution_ids_json, start_time, end_time, outcome_ids_json, "
                "evidence_refs_json, provenance_refs_json, policy_versions_json, "
                "status, created_at FROM episode_index "
                "WHERE outcome_ids_json LIKE ? ORDER BY start_time DESC",
                (f'%"{outcome_id}"%',),
            ).fetchall()
            return [self._episode_row_to_dict(r) for r in rows]

    @staticmethod
    def _episode_row_to_dict(r) -> dict[str, Any]:
        return {
            "episode_id": r[0],
            "episode_type": r[1],
            "root_trigger_id": r[2],
            "mission_ids": json.loads(r[3]) if r[3] else [],
            "institution_ids": json.loads(r[4]) if r[4] else [],
            "start_time": r[5],
            "end_time": r[6],
            "outcome_ids": json.loads(r[7]) if r[7] else [],
            "evidence_refs": json.loads(r[8]) if r[8] else [],
            "provenance_refs": json.loads(r[9]) if r[9] else [],
            "policy_versions": json.loads(r[10]) if r[10] else [],
            "status": r[11],
            "created_at": r[12],
        }

    # ---- executive memory: semantic memory (F9 Phase H) ----

    @staticmethod
    def compute_semantic_basis_hash(claim_class: str, statement: str, evidence_refs: list[str]) -> str:
        """Semantic-memory idempotency key: same claim_class + statement +
        evidence basis => same hash => no duplicate ACTIVE record."""
        import hashlib
        basis = json.dumps(
            {"claim_class": claim_class, "statement": statement, "evidence_refs": sorted(evidence_refs or [])},
            sort_keys=True,
        )
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()

    def find_semantic_by_basis_hash(self, semantic_basis_hash: str) -> Optional[dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT semantic_id, statement, claim_class, evidence_refs_json, "
                "provenance_refs_json, valid_from, valid_until, confidence_basis, "
                "status, supersedes_id, semantic_basis_hash, created_at "
                "FROM semantic_memory WHERE semantic_basis_hash = ? AND status = 'ACTIVE' "
                "ORDER BY created_at DESC LIMIT 1",
                (semantic_basis_hash,),
            ).fetchone()
            if not row:
                return None
            return self._semantic_row_to_dict(row)

    def record_semantic_memory(self, semantic_dict: dict[str, Any], enforce_idempotency: bool = True) -> tuple[str, bool]:
        """Record a semantic memory item.

        Idempotent: same claim_class + statement + evidence_refs basis
        while an ACTIVE record already exists => returns the existing
        semantic_id, no duplicate created.
        """
        basis_hash = self.compute_semantic_basis_hash(
            semantic_dict.get("claim_class"), semantic_dict.get("statement"), semantic_dict.get("evidence_refs") or []
        )

        if enforce_idempotency:
            existing = self.find_semantic_by_basis_hash(basis_hash)
            if existing:
                return existing["semantic_id"], False

        with self.connection() as conn:
            conn.execute(
                "INSERT INTO semantic_memory "
                "(semantic_id, statement, claim_class, evidence_refs_json, provenance_refs_json, "
                "valid_from, valid_until, confidence_basis, status, supersedes_id, "
                "semantic_basis_hash, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    semantic_dict.get("semantic_id"),
                    semantic_dict.get("statement"),
                    semantic_dict.get("claim_class"),
                    json.dumps(semantic_dict.get("evidence_refs", [])),
                    json.dumps(semantic_dict.get("provenance_refs", [])),
                    semantic_dict.get("valid_from", datetime.now(timezone.utc).isoformat()),
                    semantic_dict.get("valid_until"),
                    semantic_dict.get("confidence_basis"),
                    semantic_dict.get("status", "ACTIVE"),
                    semantic_dict.get("supersedes_id"),
                    basis_hash,
                    semantic_dict.get("created_at", datetime.now(timezone.utc).isoformat()),
                ),
            )
        return semantic_dict.get("semantic_id"), True

    def update_semantic_status(self, semantic_id: str, status: str, valid_until: Optional[str] = None) -> None:
        """Transition a semantic memory item's status. Never deletes -- history preserved."""
        with self.connection() as conn:
            if valid_until:
                conn.execute(
                    "UPDATE semantic_memory SET status = ?, valid_until = ? WHERE semantic_id = ?",
                    (status, valid_until, semantic_id),
                )
            else:
                conn.execute(
                    "UPDATE semantic_memory SET status = ? WHERE semantic_id = ?",
                    (status, semantic_id),
                )

    def get_semantic_memory(self, semantic_id: str) -> Optional[dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT semantic_id, statement, claim_class, evidence_refs_json, "
                "provenance_refs_json, valid_from, valid_until, confidence_basis, "
                "status, supersedes_id, semantic_basis_hash, created_at "
                "FROM semantic_memory WHERE semantic_id = ?",
                (semantic_id,),
            ).fetchone()
            if not row:
                return None
            return self._semantic_row_to_dict(row)

    def find_semantic_by_claim_class(self, claim_class: str, status: Optional[str] = None) -> list[dict[str, Any]]:
        with self.connection() as conn:
            if status:
                rows = conn.execute(
                    "SELECT semantic_id, statement, claim_class, evidence_refs_json, "
                    "provenance_refs_json, valid_from, valid_until, confidence_basis, "
                    "status, supersedes_id, semantic_basis_hash, created_at "
                    "FROM semantic_memory WHERE claim_class = ? AND status = ? ORDER BY created_at DESC",
                    (claim_class, status),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT semantic_id, statement, claim_class, evidence_refs_json, "
                    "provenance_refs_json, valid_from, valid_until, confidence_basis, "
                    "status, supersedes_id, semantic_basis_hash, created_at "
                    "FROM semantic_memory WHERE claim_class = ? ORDER BY created_at DESC",
                    (claim_class,),
                ).fetchall()
            return [self._semantic_row_to_dict(r) for r in rows]

    @staticmethod
    def _semantic_row_to_dict(r) -> dict[str, Any]:
        return {
            "semantic_id": r[0],
            "statement": r[1],
            "claim_class": r[2],
            "evidence_refs": json.loads(r[3]) if r[3] else [],
            "provenance_refs": json.loads(r[4]) if r[4] else [],
            "valid_from": r[5],
            "valid_until": r[6],
            "confidence_basis": r[7],
            "status": r[8],
            "supersedes_id": r[9],
            "semantic_basis_hash": r[10],
            "created_at": r[11],
        }

    # ---- executive event inbox (F9 Phase I) ----

    def find_event_by_dedup_key(self, dedup_key: str) -> Optional[dict[str, Any]]:
        """Find any existing event (any status) with this semantic dedup_key."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT event_id, resulting_delegation_id, status FROM event_inbox "
                "WHERE dedup_key = ? ORDER BY received_at ASC LIMIT 1",
                (dedup_key,),
            ).fetchone()
            if not row:
                return None
            return {"event_id": row[0], "resulting_delegation_id": row[1], "status": row[2]}

    def record_event(self, event_dict: dict[str, Any]) -> tuple[str, bool]:
        """Record an event in the persistent inbox.

        Idempotent on event_id (exact replay) AND on dedup_key (semantic
        duplicate under a new event_id, e.g. provider replay). Returns
        (event_id_to_use, is_new). If a duplicate exists, the EXISTING
        event_id is returned and no new row is inserted.
        """
        with self.connection() as conn:
            existing_by_id = conn.execute(
                "SELECT event_id FROM event_inbox WHERE event_id = ?",
                (event_dict.get("event_id"),),
            ).fetchone()
            if existing_by_id:
                return existing_by_id[0], False

        existing_by_dedup = self.find_event_by_dedup_key(event_dict.get("dedup_key"))
        if existing_by_dedup:
            return existing_by_dedup["event_id"], False

        with self.connection() as conn:
            conn.execute(
                "INSERT INTO event_inbox "
                "(event_id, event_type, occurred_at, received_at, source_institution, "
                "subject, payload_ref, evidence_refs_json, provenance_refs_json, "
                "correlation_id, causation_id, dedup_key, policy_context, schema_version, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_dict.get("event_id"),
                    event_dict.get("event_type"),
                    event_dict.get("occurred_at"),
                    event_dict.get("received_at", datetime.now(timezone.utc).isoformat()),
                    event_dict.get("source_institution"),
                    event_dict.get("subject"),
                    event_dict.get("payload_ref"),
                    json.dumps(event_dict.get("evidence_refs", [])),
                    json.dumps(event_dict.get("provenance_refs", [])),
                    event_dict.get("correlation_id"),
                    event_dict.get("causation_id"),
                    event_dict.get("dedup_key"),
                    event_dict.get("policy_context"),
                    event_dict.get("schema_version"),
                    "RECEIVED",
                ),
            )
        return event_dict.get("event_id"), True

    def update_event_status(
        self,
        event_id: str,
        status: str,
        resulting_delegation_id: Optional[str] = None,
        error_class: Optional[str] = None,
        error_reason: Optional[str] = None,
        increment_attempt: bool = False,
    ) -> None:
        """Update event inbox status in place. Full status history lives in
        the event's causally-linked mission_lifecycle_event trail, not here --
        this row tracks the event's OWN processing state only."""
        with self.connection() as conn:
            sets = ["status = ?"]
            values: list[Any] = [status]
            if resulting_delegation_id is not None:
                sets.append("resulting_delegation_id = ?")
                values.append(resulting_delegation_id)
            if error_class is not None:
                sets.append("last_error_class = ?")
                values.append(error_class)
            if error_reason is not None:
                sets.append("last_error_reason = ?")
                values.append(error_reason)
            if increment_attempt:
                sets.append("attempt_count = attempt_count + 1")
            if status == "DEAD_LETTER":
                sets.append("dead_lettered_at = ?")
                values.append(datetime.now(timezone.utc).isoformat())
            values.append(event_id)
            conn.execute(f"UPDATE event_inbox SET {', '.join(sets)} WHERE event_id = ?", values)

    def get_event(self, event_id: str) -> Optional[dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT event_id, event_type, occurred_at, received_at, source_institution, "
                "subject, payload_ref, evidence_refs_json, provenance_refs_json, "
                "correlation_id, causation_id, dedup_key, policy_context, schema_version, "
                "status, attempt_count, last_error_class, last_error_reason, "
                "dead_lettered_at, resulting_delegation_id "
                "FROM event_inbox WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if not row:
                return None
            return self._event_row_to_dict(row)

    def list_events_by_status(self, status: str) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT event_id, event_type, occurred_at, received_at, source_institution, "
                "subject, payload_ref, evidence_refs_json, provenance_refs_json, "
                "correlation_id, causation_id, dedup_key, policy_context, schema_version, "
                "status, attempt_count, last_error_class, last_error_reason, "
                "dead_lettered_at, resulting_delegation_id "
                "FROM event_inbox WHERE status = ? ORDER BY received_at ASC",
                (status,),
            ).fetchall()
            return [self._event_row_to_dict(r) for r in rows]

    @staticmethod
    def _event_row_to_dict(r) -> dict[str, Any]:
        return {
            "event_id": r[0],
            "event_type": r[1],
            "occurred_at": r[2],
            "received_at": r[3],
            "source_institution": r[4],
            "subject": r[5],
            "payload_ref": r[6],
            "evidence_refs": json.loads(r[7]) if r[7] else [],
            "provenance_refs": json.loads(r[8]) if r[8] else [],
            "correlation_id": r[9],
            "causation_id": r[10],
            "dedup_key": r[11],
            "policy_context": r[12],
            "schema_version": r[13],
            "status": r[14],
            "attempt_count": r[15],
            "last_error_class": r[16],
            "last_error_reason": r[17],
            "dead_lettered_at": r[18],
            "resulting_delegation_id": r[19],
        }

    # ---- atomic cross-process lease claim (F9 Phase I) ----

    def atomic_claim_mission(
        self,
        delegation_id: str,
        lease_id: str,
        actor: str,
        reason: str,
        policy_version: str = "F9.0",
        eligible_states: tuple[str, ...] = ("QUEUED", "RETRYABLE"),
        retries: int = 5,
        retry_backoff_seconds: float = 0.05,
        institution_id: Optional[str] = None,
    ) -> tuple[bool, str]:
        """Atomically claim a mission's lease across processes.

        Uses BEGIN IMMEDIATE to acquire an exclusive write lock on the
        SQLite database BEFORE reading current state, closing the
        check-then-write race window that a plain read + separate write
        would leave open between two OS processes. SQLite serializes
        IMMEDIATE transactions across all connections (including from other
        processes) via its file-level locking -- only one process can hold
        the write lock at a time; the loser gets SQLITE_BUSY and retries
        with backoff, or observes the winner's committed state.

        F10C.1: if `institution_id` is given, capacity is checked INSIDE
        the same locked transaction as the state check -- capacity was
        previously advisory-only (is_institution_admissible() had to be
        called separately, and nothing stopped a claim from succeeding
        while an institution was already at max_concurrent_missions).
        This closes that gap structurally: passing institution_id makes
        capacity enforcement part of the atomic claim itself, not a
        convention the caller must remember.

        Returns (won, reason). Exactly one caller across any number of
        concurrent processes racing on the same delegation_id can win.
        """
        import time
        import uuid

        last_error = ""
        for attempt in range(retries):
            conn = self._connect()
            conn.isolation_level = None  # manual transaction control for BEGIN IMMEDIATE
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT new_state FROM mission_lifecycle_event "
                    "WHERE delegation_id = ? ORDER BY timestamp DESC, rowid DESC LIMIT 1",
                    (delegation_id,),
                ).fetchone()
                current_state = row[0] if row else None

                if current_state not in eligible_states:
                    conn.execute("ROLLBACK")
                    return False, f"not eligible: current_state={current_state}, expected one of {eligible_states}"

                if institution_id is not None:
                    cap_row = conn.execute(
                        "SELECT availability_state, circuit_state, active_missions, max_concurrent_missions "
                        "FROM institution_capacity WHERE institution_id = ?",
                        (institution_id,),
                    ).fetchone()
                    if cap_row is not None:
                        availability_state, circuit_state, active_missions, max_concurrent = cap_row
                        if availability_state == "UNAVAILABLE" or circuit_state == "OPEN":
                            conn.execute("ROLLBACK")
                            return False, f"institution {institution_id} not admissible: availability={availability_state}, circuit={circuit_state}"
                        if active_missions >= max_concurrent:
                            conn.execute("ROLLBACK")
                            return False, f"institution {institution_id} at capacity: active={active_missions}/{max_concurrent}"

                event_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO mission_lifecycle_event "
                    "(event_id, delegation_id, previous_state, new_state, timestamp, "
                    "actor, reason, policy_version, lease_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        event_id,
                        delegation_id,
                        current_state,
                        "CLAIMED",
                        datetime.now(timezone.utc).isoformat(),
                        actor,
                        reason,
                        policy_version,
                        lease_id,
                    ),
                )
                conn.commit()
                return True, f"claimed by {actor} with lease {lease_id}"
            except sqlite3.OperationalError as e:
                last_error = str(e)
                try:
                    conn.rollback()
                except Exception:
                    pass
                time.sleep(retry_backoff_seconds * (attempt + 1))
            finally:
                conn.close()

        return False, f"failed to acquire lock after {retries} attempts: {last_error}"

    # ---- loop observability counters (F9 Phase I) ----

    def increment_counter(self, counter_name: str, by: int = 1) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO loop_observability (counter_name, counter_value) VALUES (?, ?) "
                "ON CONFLICT(counter_name) DO UPDATE SET counter_value = counter_value + ?",
                (counter_name, by, by),
            )

    def get_counter(self, counter_name: str) -> int:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT counter_value FROM loop_observability WHERE counter_name = ?",
                (counter_name,),
            ).fetchone()
            return row[0] if row else 0

    def get_all_counters(self) -> dict[str, int]:
        with self.connection() as conn:
            rows = conn.execute("SELECT counter_name, counter_value FROM loop_observability").fetchall()
            return {name: value for name, value in rows}

    # ---- shadow decisions (F10B) ----

    @staticmethod
    def compute_shadow_basis_hash(source_institution: str, source_cycle_id: Optional[str], evidence_refs: list[str]) -> str:
        """Semantic idempotency key: same institution + cycle_id + evidence
        basis => same shadow decision, never duplicated on replay."""
        import hashlib
        basis = json.dumps(
            {"source_institution": source_institution, "source_cycle_id": source_cycle_id, "evidence_refs": sorted(evidence_refs or [])},
            sort_keys=True,
        )
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()

    def find_shadow_decision_by_basis_hash(self, source_institution: str, basis_hash: str) -> Optional[dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT shadow_decision_id FROM shadow_decision WHERE source_institution = ? AND semantic_basis_hash = ? "
                "ORDER BY created_at ASC LIMIT 1",
                (source_institution, basis_hash),
            ).fetchone()
            return {"shadow_decision_id": row[0]} if row else None

    def record_shadow_decision(self, decision: dict[str, Any], enforce_idempotency: bool = True) -> tuple[str, bool]:
        """Persist a shadow decision. Idempotent on (institution, cycle_id,
        evidence basis): a replayed identical input returns the EXISTING
        shadow_decision_id, no duplicate row -- receipts of the replay
        attempt are the caller's concern (kernel-level DUPLICATE
        classification already covers that), this table stays one row per
        genuinely distinct semantic decision."""
        basis_hash = self.compute_shadow_basis_hash(
            decision["source_institution"], decision.get("source_cycle_id"), decision.get("evidence_refs") or []
        )

        if enforce_idempotency:
            existing = self.find_shadow_decision_by_basis_hash(decision["source_institution"], basis_hash)
            if existing:
                return existing["shadow_decision_id"], False

        with self.connection() as conn:
            conn.execute(
                "INSERT INTO shadow_decision "
                "(shadow_decision_id, source_institution, source_cycle_id, semantic_basis_hash, "
                "attention_class, attention_score, priority_class, priority_score, "
                "recommended_action, recommended_recipient, authority_required, "
                "would_dispatch, authority_would_have_allowed, blocked_reason, "
                "evidence_refs_json, policy_version, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    decision["shadow_decision_id"],
                    decision["source_institution"],
                    decision.get("source_cycle_id"),
                    basis_hash,
                    decision.get("attention_class"),
                    decision.get("attention_score"),
                    decision.get("priority_class"),
                    decision.get("priority_score"),
                    decision.get("recommended_action"),
                    decision.get("recommended_recipient"),
                    decision.get("authority_required"),
                    1 if decision.get("would_dispatch") else 0,
                    (1 if decision.get("authority_would_have_allowed") else 0) if decision.get("authority_would_have_allowed") is not None else None,
                    decision.get("blocked_reason"),
                    json.dumps(decision.get("evidence_refs", [])),
                    decision.get("policy_version", "F9.0"),
                    decision.get("created_at", datetime.now(timezone.utc).isoformat()),
                ),
            )
        return decision["shadow_decision_id"], True

    def get_shadow_decision(self, shadow_decision_id: str) -> Optional[dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT shadow_decision_id, source_institution, source_cycle_id, "
                "attention_class, attention_score, priority_class, priority_score, "
                "recommended_action, recommended_recipient, authority_required, "
                "would_dispatch, authority_would_have_allowed, blocked_reason, "
                "evidence_refs_json, policy_version, created_at "
                "FROM shadow_decision WHERE shadow_decision_id = ?",
                (shadow_decision_id,),
            ).fetchone()
            if not row:
                return None
            return self._shadow_decision_row_to_dict(row)

    def list_shadow_decisions(self, source_institution: Optional[str] = None) -> list[dict[str, Any]]:
        with self.connection() as conn:
            if source_institution:
                rows = conn.execute(
                    "SELECT shadow_decision_id, source_institution, source_cycle_id, "
                    "attention_class, attention_score, priority_class, priority_score, "
                    "recommended_action, recommended_recipient, authority_required, "
                    "would_dispatch, authority_would_have_allowed, blocked_reason, "
                    "evidence_refs_json, policy_version, created_at "
                    "FROM shadow_decision WHERE source_institution = ? ORDER BY created_at DESC",
                    (source_institution,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT shadow_decision_id, source_institution, source_cycle_id, "
                    "attention_class, attention_score, priority_class, priority_score, "
                    "recommended_action, recommended_recipient, authority_required, "
                    "would_dispatch, authority_would_have_allowed, blocked_reason, "
                    "evidence_refs_json, policy_version, created_at "
                    "FROM shadow_decision ORDER BY created_at DESC",
                ).fetchall()
            return [self._shadow_decision_row_to_dict(r) for r in rows]

    @staticmethod
    def _shadow_decision_row_to_dict(r) -> dict[str, Any]:
        return {
            "shadow_decision_id": r[0],
            "source_institution": r[1],
            "source_cycle_id": r[2],
            "attention_class": r[3],
            "attention_score": r[4],
            "priority_class": r[5],
            "priority_score": r[6],
            "recommended_action": r[7],
            "recommended_recipient": r[8],
            "authority_required": r[9],
            "would_dispatch": bool(r[10]),
            "authority_would_have_allowed": bool(r[11]) if r[11] is not None else None,
            "blocked_reason": r[12],
            "evidence_refs": json.loads(r[13]) if r[13] else [],
            "policy_version": r[14],
            "created_at": r[15],
        }
