#!/usr/bin/env python3
"""One-off repair script for Defect E1 (Evidence Ledger chain forks).

Background
----------
`EvidenceLedger.record_event()` used to read the current chain tail
(`_get_last_record_hash()`) and INSERT the new record as two separate,
unsynchronized SQLite statements. Under concurrent writers this is a
classic TOCTOU race: two writers can both read the same tail `record_hash`
as their `prev_hash` and both commit, producing two records that share one
parent -- a fork. `EvidenceLedger.verify_chain()` walks the chain assuming
exactly one child per parent, so a forked ledger fails verification.

The race itself is fixed in `observatory/evidence_ledger.py` (the read +
insert is now wrapped in a single `BEGIN IMMEDIATE` transaction guarded by
a process-local lock). This script is the one-off data repair for ledgers
that already accumulated forks before that fix shipped (85 forks were
observed in the production ledger).

What this script does
----------------------
1. Loads every row from the `events` table.
2. Detects forks: any `prev_hash` value claimed by more than one record.
3. Rebuilds a single canonical linear order for the *whole* table, using
   `(timestamp, rowid)` as the tiebreak -- this is the same ordering
   `verify_chain()` and `query_events()` already use, so the repaired chain
   stays consistent with how the rest of the system reads the ledger.
4. Recomputes `prev_hash` for every record from its predecessor in that
   canonical order, and recomputes `record_hash` with the exact same
   hashing routine `EvidenceLedger` uses (imported directly from
   `observatory.evidence_ledger`, so this script cannot drift from the
   real algorithm).
5. Emits `UPDATE` statements only for rows whose `prev_hash` and/or
   `record_hash` actually change relative to what's stored today.

This script NEVER writes to the database by default -- it prints the SQL
it would run. Pass --apply to execute it inside a single transaction
against the target database (a timestamped `.bak` copy is made first).

Usage
-----
    # Dry run (default): print the repair SQL, change nothing.
    python3 scripts/repair_evidence_ledger_forks.py /path/to/evidence_ledger.db

    # Apply the fix (makes a .bak backup first).
    python3 scripts/repair_evidence_ledger_forks.py /path/to/evidence_ledger.db --apply
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from observatory.evidence_ledger import (  # noqa: E402
    GENESIS_HASH,
    _HASHED_COLUMNS,
    EvidenceLedger,
)


def _load_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        "SELECT rowid AS _rowid, * FROM events ORDER BY timestamp ASC, rowid ASC"
    ).fetchall()


def detect_forks(rows: list[sqlite3.Row]) -> dict[str, list[sqlite3.Row]]:
    """Return {prev_hash: [rows...]} for every prev_hash claimed by >1 row."""
    by_prev: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_prev.setdefault(row["prev_hash"], []).append(row)
    return {prev: rs for prev, rs in by_prev.items() if len(rs) > 1}


def build_repair_plan(rows: list[sqlite3.Row]) -> list[tuple[str, str, str]]:
    """Rebuild the canonical linear chain and return the diffs needed to fix it.

    Returns a list of (event_id, new_prev_hash, new_record_hash) for every
    row whose stored prev_hash/record_hash differs from the recomputed
    canonical value. Rows already correct are omitted.
    """
    plan: list[tuple[str, str, str]] = []
    expected_prev_hash = GENESIS_HASH

    for row in rows:
        record_dict = {col: row[col] for col in _HASHED_COLUMNS}
        record_dict["prev_hash"] = expected_prev_hash

        new_record_hash = EvidenceLedger._compute_record_hash(record_dict)

        if row["prev_hash"] != expected_prev_hash or row["record_hash"] != new_record_hash:
            plan.append((row["event_id"], expected_prev_hash, new_record_hash))

        expected_prev_hash = new_record_hash

    return plan


def render_sql(plan: list[tuple[str, str, str]]) -> str:
    lines = [
        "BEGIN IMMEDIATE;",
    ]
    for event_id, new_prev_hash, new_record_hash in plan:
        lines.append(
            "UPDATE events SET prev_hash = '{prev}', record_hash = '{rec}' "
            "WHERE event_id = '{eid}';".format(
                prev=new_prev_hash, rec=new_record_hash, eid=event_id
            )
        )
    lines.append("COMMIT;")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db_path", type=Path, help="Path to the evidence ledger .db file")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually execute the repair SQL against the database (default: dry run / print only).",
    )
    args = parser.parse_args()

    if not args.db_path.exists():
        print(f"error: no such database: {args.db_path}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(args.db_path))
    rows = _load_rows(conn)

    forks = detect_forks(rows)
    print(f"# Loaded {len(rows)} events from {args.db_path}")
    print(f"# Detected {len(forks)} fork point(s) affecting "
          f"{sum(len(rs) for rs in forks.values())} record(s):")
    for prev_hash, forked_rows in forks.items():
        ids = ", ".join(r["event_id"] for r in forked_rows)
        print(f"#   prev_hash={prev_hash[:12]}... -> {len(forked_rows)} children: {ids}")

    plan = build_repair_plan(rows)
    print(f"# Repair plan touches {len(plan)} record(s) "
          f"(includes any records downstream of a fork whose prev_hash chain shifted).")
    print()

    sql = render_sql(plan)
    print(sql)

    if not args.apply:
        print(
            "\n# Dry run only -- no changes made. Re-run with --apply to execute.",
            file=sys.stderr,
        )
        return 0

    if not plan:
        print("\n# Nothing to repair.", file=sys.stderr)
        return 0

    backup_path = args.db_path.with_suffix(
        f".bak-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}{args.db_path.suffix}"
    )
    shutil.copy2(args.db_path, backup_path)
    print(f"\n# Backed up original database to {backup_path}", file=sys.stderr)

    conn.execute("BEGIN IMMEDIATE")
    try:
        for event_id, new_prev_hash, new_record_hash in plan:
            conn.execute(
                "UPDATE events SET prev_hash = ?, record_hash = ? WHERE event_id = ?",
                (new_prev_hash, new_record_hash, event_id),
            )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"# Applied {len(plan)} update(s) to {args.db_path}.", file=sys.stderr)

    # Verify the repair with the real EvidenceLedger.verify_chain().
    ledger = EvidenceLedger(args.db_path)
    ok, bad_id = ledger.verify_chain()
    ledger.close()
    if ok:
        print("# verify_chain() -> True. Chain is now linear and valid.", file=sys.stderr)
        return 0
    print(f"# verify_chain() -> False at {bad_id}. Manual investigation required.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
