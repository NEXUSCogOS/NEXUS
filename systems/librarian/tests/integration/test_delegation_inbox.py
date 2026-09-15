"""Delegation delivery mechanism tests (runtime/delegation_inbox.py).

Proves delivery is persistent, idempotent, auditable, and restart-safe
(mission section 17) using the REAL shared federation store -- not a
direct Python function call between institutions.
"""

from __future__ import annotations

from persistence.db import FederationStore
from runtime.delegation_inbox import poll_and_execute


def _make_proposal(idempotency_key="k1", proposal_id="p1"):
    return {
        "mission_id": "m1",
        "issuer": "nexus_federation",
        "recipient": "librarian",
        "objective": "ingestion provenance dedup chunk",
        "reason": "test",
        "evidence_refs": [],
        "priority": 1,
        "authority": "ANALYSE",
        "constraints": [],
        "resource_budget": {
            "cpu_seconds": 1.0, "memory_bytes": 1, "elapsed_seconds": 1.0,
            "local_storage_bytes": 1, "external_storage_bytes": 0,
            "api_cost_usd": 0.0, "model_tokens": 0, "basis": "test",
        },
        "ttl_deadline": None,
        "success_criteria": [],
        "risk_class": "LOW",
        "parent_mission": "m1",
        "requested_output_contract": "InstitutionalReport v1.1.0",
        "created_at": "2026-08-27T00:00:00+00:00",
        "proposal_id": proposal_id,
        "idempotency_key": idempotency_key,
        "provenance_id": None,
    }


def test_pending_delegation_is_claimed_and_executed(tmp_path, real_data_dir):
    store = FederationStore(tmp_path / "f.db")
    store.append_delegation(_make_proposal())

    executed = poll_and_execute(store, data_dir=real_data_dir)
    assert len(executed) == 1
    assert executed[0].proposal_id == "p1"
    assert store.get_delivery_record("p1")["executed_at"] is not None


def test_claiming_is_idempotent_no_double_execution(tmp_path, real_data_dir):
    store = FederationStore(tmp_path / "f.db")
    store.append_delegation(_make_proposal())

    first = poll_and_execute(store, data_dir=real_data_dir)
    second = poll_and_execute(store, data_dir=real_data_dir)
    assert len(first) == 1
    assert len(second) == 0  # already claimed, not re-executed


def test_delivery_survives_restart(tmp_path, real_data_dir):
    db_path = tmp_path / "f.db"
    store1 = FederationStore(db_path)
    store1.append_delegation(_make_proposal())
    poll_and_execute(store1, data_dir=real_data_dir)

    # "restart": brand-new store object, same file
    store2 = FederationStore(db_path)
    record = store2.get_delivery_record("p1")
    assert record is not None
    assert record["executed_at"] is not None
    # And a second poll on the "restarted" store still claims nothing new.
    assert poll_and_execute(store2, data_dir=real_data_dir) == []


def test_unrelated_recipient_delegations_are_not_claimed(tmp_path, real_data_dir):
    store = FederationStore(tmp_path / "f.db")
    proposal = _make_proposal()
    proposal["recipient"] = "sentinel"
    store.append_delegation(proposal)

    executed = poll_and_execute(store, data_dir=real_data_dir)
    assert executed == []
