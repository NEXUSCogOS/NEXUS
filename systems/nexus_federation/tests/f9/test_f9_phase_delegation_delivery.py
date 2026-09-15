"""F10C.1: bounded tests for the shared specialist-execution boundary.

runtime/delegation_delivery.py::claim_and_execute() is production
architecture: the single point where "claim must be authoritative" is
enforced, closing the F10C duplicate-outcome defect (a wrapper script that
called claim_delegation() but proceeded regardless of its return value).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from executive.mission_state import MissionState
from persistence.db import FederationStore
from runtime.delegation_delivery import claim_and_execute


def test_first_claim_executes_mission():
    with tempfile.TemporaryDirectory() as d:
        store = FederationStore(Path(d) / "test.db")
        calls = []
        result = claim_and_execute(store, "deleg-1", "librarian", lambda: calls.append(1) or "ok")
        assert result.claimed is True
        assert result.executed is True
        assert result.status == "EXECUTED"
        assert result.mission_result == "ok"
        assert len(calls) == 1


def test_replay_does_not_execute_mission():
    with tempfile.TemporaryDirectory() as d:
        store = FederationStore(Path(d) / "test.db")
        calls = []
        mission_fn = lambda: calls.append(1) or "ok"

        result1 = claim_and_execute(store, "deleg-1", "librarian", mission_fn)
        result2 = claim_and_execute(store, "deleg-1", "librarian", mission_fn)

        assert result1.executed is True
        assert result2.claimed is False
        assert result2.executed is False
        assert result2.status == "ALREADY_CLAIMED_NO_EXECUTION"
        assert len(calls) == 1, "mission_fn must not be invoked on an already-claimed delegation"


def test_replay_survives_fresh_store_instance():
    """Proves the guard is persistent (FederationStore-backed), not process-local."""
    with tempfile.TemporaryDirectory() as d:
        db_path = Path(d) / "test.db"
        store_a = FederationStore(db_path)
        claim_and_execute(store_a, "deleg-1", "librarian", lambda: "first")

        store_b = FederationStore(db_path)  # fresh instance, same file
        calls = []
        result = claim_and_execute(store_b, "deleg-1", "librarian", lambda: calls.append(1))
        assert result.status == "ALREADY_CLAIMED_NO_EXECUTION"
        assert len(calls) == 0


def test_mission_fn_exception_is_not_swallowed():
    """claim_and_execute must not hide a specialist failure."""
    with tempfile.TemporaryDirectory() as d:
        store = FederationStore(Path(d) / "test.db")

        def failing_mission():
            raise RuntimeError("specialist failure")

        try:
            claim_and_execute(store, "deleg-1", "librarian", failing_mission)
            assert False, "exception should have propagated"
        except RuntimeError as e:
            assert str(e) == "specialist failure"


def test_owns_no_state_itself():
    """claim_and_execute has no module-level mutable state; two independent
    FederationStore instances behave completely independently."""
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        store1 = FederationStore(Path(d1) / "a.db")
        store2 = FederationStore(Path(d2) / "b.db")

        r1 = claim_and_execute(store1, "same-delegation-id", "librarian", lambda: "x")
        r2 = claim_and_execute(store2, "same-delegation-id", "librarian", lambda: "y")

        assert r1.executed is True
        assert r2.executed is True, "independent stores must not share claim state"
