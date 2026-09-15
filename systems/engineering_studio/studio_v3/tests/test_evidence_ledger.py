"""Tests for the Evidence Ledger (Engineering Observatory, Engineering Studio v4)."""

import sqlite3
import sys
import threading
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from observatory.evidence_ledger import EvidenceLedger, TruncationDetected


@pytest.fixture
def ledger(tmp_path):
    db_path = tmp_path / "evidence.db"
    led = EvidenceLedger(db_path)
    yield led
    led.close()


def test_record_event_returns_uuid_and_is_retrievable(ledger):
    event_id = ledger.record_event(
        agent="tester",
        action="run_tests",
        input_data={"foo": "bar"},
        output_data={"result": 1},
    )

    # Assert event_id is UUID-shaped (valid hex UUID4 string).
    parsed = uuid.UUID(event_id)
    assert parsed.hex == event_id or str(parsed).replace("-", "") == event_id

    event = ledger.get_event(event_id)
    assert event is not None
    assert event["agent"] == "tester"
    assert event["action"] == "run_tests"
    assert event["input_data"] == {"foo": "bar"}
    assert event["output_data"] == {"result": 1}
    assert event["verification_status"] == "unverified"
    assert event["prev_hash"] == "0" * 64


def test_three_events_produce_valid_chain(ledger):
    ledger.record_event(agent="a1", action="act1")
    ledger.record_event(agent="a2", action="act2")
    ledger.record_event(agent="a3", action="act3")

    ok, bad_id = ledger.verify_chain()
    assert ok is True
    assert bad_id is None


def test_tampering_detected_by_verify_chain(ledger, tmp_path):
    id1 = ledger.record_event(agent="a1", action="act1", output_data={"v": 1})
    ledger.record_event(agent="a2", action="act2", output_data={"v": 2})
    ledger.record_event(agent="a3", action="act3", output_data={"v": 3})

    # Sanity: chain is valid before tampering.
    ok, bad_id = ledger.verify_chain()
    assert ok is True

    # Tamper directly via raw SQL on the underlying sqlite file.
    raw_conn = sqlite3.connect(str(ledger.db_path))
    raw_conn.execute(
        "UPDATE events SET output_data = ? WHERE event_id = ?",
        ('{"v": 9999}', id1),
    )
    raw_conn.commit()
    raw_conn.close()

    ok, bad_id = ledger.verify_chain()
    assert ok is False
    assert bad_id == id1


def test_query_events_filters_by_agent_and_action(ledger):
    ledger.record_event(agent="agent_a", action="build")
    ledger.record_event(agent="agent_a", action="test")
    ledger.record_event(agent="agent_b", action="build")

    by_agent = ledger.query_events(agent="agent_a")
    assert len(by_agent) == 2
    assert all(e["agent"] == "agent_a" for e in by_agent)

    by_action = ledger.query_events(action="build")
    assert len(by_action) == 2
    assert all(e["action"] == "build" for e in by_action)

    by_both = ledger.query_events(agent="agent_a", action="build")
    assert len(by_both) == 1
    assert by_both[0]["agent"] == "agent_a"
    assert by_both[0]["action"] == "build"


def test_concurrent_writes_maintain_chain_integrity(ledger):
    """Defect E1 regression test.

    Spawns 10 threads, each writing 5 events concurrently through the same
    EvidenceLedger instance. Before the BEGIN IMMEDIATE fix, concurrent
    readers of _get_last_record_hash() could observe the same tail hash and
    both chain new records from it, forking the chain (this reproduced the
    85 forks seen in production). After the fix, all 50 events must form a
    single linear chain.
    """
    num_threads = 10
    events_per_thread = 5
    errors: list[BaseException] = []

    def writer(thread_index: int) -> None:
        try:
            for i in range(events_per_thread):
                ledger.record_event(
                    agent=f"agent_{thread_index}",
                    action=f"action_{i}",
                    input_data={"thread": thread_index, "seq": i},
                )
        except BaseException as exc:  # noqa: BLE001 - capture for main thread
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(t,)) for t in range(num_threads)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert not errors, f"writer threads raised: {errors}"

    all_events = ledger.query_events()
    assert len(all_events) == num_threads * events_per_thread

    # No two records may share the same prev_hash (that is exactly what a
    # fork looks like: two children pointing at the same parent).
    rows = ledger._conn.execute("SELECT prev_hash, COUNT(*) c FROM events GROUP BY prev_hash HAVING c > 1").fetchall()
    assert rows == [], f"forked prev_hash values found: {[dict(r) for r in rows]}"

    ok, bad_id = ledger.verify_chain()
    assert ok is True, f"chain broken at event {bad_id}"


def test_tail_truncation_detected(ledger):
    """Defect E2 regression test.

    Deleting the last records leaves an internally-consistent (linear)
    chain with no dangling forward reference, so a naive verifier sees
    nothing wrong. The _chain_metadata total_events counter, updated
    atomically with every insert, catches the discrepancy.
    """
    ledger.record_event(agent="a1", action="act1")
    ledger.record_event(agent="a2", action="act2")
    ledger.record_event(agent="a3", action="act3")
    ledger.record_event(agent="a4", action="act4")

    ok, bad_id = ledger.verify_chain()
    assert ok is True

    raw_conn = sqlite3.connect(str(ledger.db_path))
    raw_conn.execute(
        "DELETE FROM events WHERE rowid IN (SELECT rowid FROM events ORDER BY rowid DESC LIMIT 2)"
    )
    raw_conn.commit()
    raw_conn.close()

    with pytest.raises(TruncationDetected):
        ledger.verify_chain()


def test_non_monotonic_clock_no_false_positive(ledger):
    """Defect E3 regression test.

    verify_chain() must order by rowid (actual insertion/chain order), not
    by timestamp. A record inserted later in the chain but carrying an
    earlier wall-clock timestamp than its predecessor (e.g. NTP skew, a
    manual clock adjustment) must not be mistaken for a broken chain: the
    hash linkage (prev_hash) is what defines chain order, not timestamp.
    """
    from observatory.evidence_ledger import EvidenceLedger as _EL

    ledger.record_event(agent="a1", action="act1")
    ledger.record_event(agent="a2", action="act2")

    ok, bad_id = ledger.verify_chain()
    assert ok is True

    # Manually append a third record, correctly chained via prev_hash, but
    # with a timestamp earlier than the previous record's - simulating a
    # non-monotonic clock. If verify_chain() ordered by timestamp, this
    # record would sort before its predecessor and the prev_hash linkage
    # would appear broken.
    raw_conn = sqlite3.connect(str(ledger.db_path))
    raw_conn.row_factory = sqlite3.Row
    prev_hash = raw_conn.execute(
        "SELECT record_hash FROM events ORDER BY rowid DESC LIMIT 1"
    ).fetchone()["record_hash"]

    record_dict = {
        "event_id": "manual-skewed-event",
        "timestamp": "2000-01-01T00:00:00+00:00",  # far in the past
        "agent": "a3",
        "action": "act3",
        "input_data": None,
        "output_data": None,
        "test_result": None,
        "resource_cost": None,
        "files_modified": None,
        "git_commit_hash": None,
        "prev_hash": prev_hash,
    }
    record_hash = _EL._compute_record_hash(record_dict)

    raw_conn.execute(
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
            "unverified",
            record_dict["prev_hash"],
            record_hash,
        ),
    )
    raw_conn.execute(
        "UPDATE _chain_metadata SET total_events = total_events + 1, chain_length_hash = ?",
        (_EL._compute_chain_length_hash(3, record_hash),),
    )
    raw_conn.commit()
    raw_conn.close()

    ok, bad_id = ledger.verify_chain()
    assert ok is True
    assert bad_id is None


def test_mid_deletion_detected(ledger):
    """Defect E2 regression test (mid-chain variant).

    Deleting a record in the middle of the chain breaks the prev_hash
    linkage for the following record, and also trips the total_events
    count check. Either way, verify_chain() must not report success.
    """
    ledger.record_event(agent="a1", action="act1")
    id2 = ledger.record_event(agent="a2", action="act2")
    ledger.record_event(agent="a3", action="act3")
    ledger.record_event(agent="a4", action="act4")

    ok, bad_id = ledger.verify_chain()
    assert ok is True

    raw_conn = sqlite3.connect(str(ledger.db_path))
    raw_conn.execute("DELETE FROM events WHERE event_id = ?", (id2,))
    raw_conn.commit()
    raw_conn.close()

    with pytest.raises(TruncationDetected):
        ledger.verify_chain()


def test_set_verification_status_does_not_change_record_hash(ledger):
    event_id = ledger.record_event(agent="a1", action="act1")

    before = ledger.get_event(event_id)
    before_hash = before["record_hash"]

    ledger.set_verification_status(event_id, "verified")

    after = ledger.get_event(event_id)
    assert after["verification_status"] == "verified"
    assert after["record_hash"] == before_hash

    # Chain must remain valid too.
    ok, bad_id = ledger.verify_chain()
    assert ok is True
