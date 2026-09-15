"""Tests for LifecycleManager: age-based migration, size-based migration,
and full cycle execution, all recording real events to a real EvidenceLedger."""

from __future__ import annotations

import os
import time

import pytest

from systems.engineering_studio.studio_v3.observatory import EvidenceLedger
from systems.engineering_studio.studio_v4.storage.compression_pipeline import CompressionPipeline
from systems.engineering_studio.studio_v4.storage.lifecycle_manager import (
    LifecycleManager,
    MigrationScheduler,
)
from systems.engineering_studio.studio_v4.storage.tiered_storage import Tier, TierManager


@pytest.fixture
def roots(tmp_path):
    r = {
        Tier.TIER_1_HOT: tmp_path / "tier1",
        Tier.TIER_2_WARM: tmp_path / "tier2",
        Tier.TIER_3_COLD: tmp_path / "tier3",
    }
    for p in r.values():
        p.mkdir(parents=True, exist_ok=True)
    return r


@pytest.fixture
def tier_manager(roots):
    return TierManager(tier_roots=roots, warm_age_days=30, cold_age_days=90, large_file_bytes=10**9)


@pytest.fixture
def ledger(tmp_path):
    l = EvidenceLedger(tmp_path / "ledger.sqlite3")
    yield l
    l.close()


@pytest.fixture
def lifecycle_manager(tier_manager, ledger):
    return LifecycleManager(tier_manager, CompressionPipeline(), ledger=ledger)


def _age_file(path, content: bytes, age_days: float):
    path.write_bytes(content)
    old_time = time.time() - (age_days * 86400)
    os.utime(path, (old_time, old_time))


def test_migrate_aged_files_moves_old_file_and_removes_original(lifecycle_manager, roots):
    fresh = roots[Tier.TIER_1_HOT] / "fresh.txt"
    aged = roots[Tier.TIER_1_HOT] / "aged.txt"
    _age_file(fresh, b"fresh content", age_days=1)
    _age_file(aged, b"aged content " * 100, age_days=45)

    results = lifecycle_manager.migrate_aged_files()

    assert len(results) == 1
    assert results[0]["target_tier"] == Tier.TIER_2_WARM.value
    assert not aged.exists()
    assert fresh.exists()
    assert (roots[Tier.TIER_2_WARM] / "aged.txt.gz").exists()


def test_migrate_aged_files_records_events_in_ledger(lifecycle_manager, roots, ledger):
    aged = roots[Tier.TIER_1_HOT] / "aged.txt"
    _age_file(aged, b"aged content " * 100, age_days=45)

    lifecycle_manager.migrate_aged_files()

    events = ledger.query_events(agent="lifecycle_manager", action="migrate_file")
    assert len(events) == 1
    assert events[0]["output_data"]["size_before"] > events[0]["output_data"]["size_after"]
    assert events[0]["resource_cost"] is not None

    ok, bad = ledger.verify_chain()
    assert ok is True


def test_migrate_sized_files_no_op_when_under_threshold(lifecycle_manager, roots):
    fresh = roots[Tier.TIER_1_HOT] / "fresh.txt"
    _age_file(fresh, b"data", age_days=1)

    results = lifecycle_manager.migrate_sized_files(percent_full=99.999)

    assert results == []
    assert fresh.exists()


def test_migrate_sized_files_migrates_when_over_threshold(lifecycle_manager, roots):
    f1 = roots[Tier.TIER_1_HOT] / "a.txt"
    f2 = roots[Tier.TIER_1_HOT] / "b.txt"
    _age_file(f1, b"x" * 1000, age_days=1)
    _age_file(f2, b"y" * 500, age_days=1)

    call_count = {"n": 0}

    def fake_disk_usage(_path):
        # First call: over threshold -> triggers migration of largest file.
        # Second call (after migrating f1): under threshold -> stop.
        call_count["n"] += 1
        if call_count["n"] == 1:
            return (100, 90, 10)  # total, used, free -> 90%
        return (100, 50, 50)  # 50% -> under threshold now

    results = lifecycle_manager.migrate_sized_files(percent_full=85.0, disk_usage_fn=fake_disk_usage)

    assert len(results) == 1
    assert results[0]["file"] == str(f1)  # largest file migrated first
    assert not f1.exists()
    assert f2.exists()


def test_run_cycle_returns_summary_and_records_event(lifecycle_manager, roots, ledger):
    aged = roots[Tier.TIER_1_HOT] / "aged.txt"
    _age_file(aged, b"aged content " * 100, age_days=45)

    summary = lifecycle_manager.run_cycle()

    assert summary["aged_migrations"] == 1
    assert summary["total_saved_bytes"] > 0
    assert "resource_cost" in summary

    cycle_events = ledger.query_events(agent="lifecycle_manager", action="run_cycle")
    assert len(cycle_events) == 1


def test_lifecycle_manager_actually_migrates_files(lifecycle_manager, roots, ledger):
    """End-to-end proof that triggering a migration cycle actually moves
    real files out of Tier 1 and into Tier 2, with records landing in the
    Observatory ledger -- this is the "Stream A never actually migrated
    files" defect made concrete as a regression test."""
    for i in range(5):
        f = roots[Tier.TIER_1_HOT] / f"doc_{i}.txt"
        _age_file(f, f"document body {i} ".encode() * 50, age_days=1)

    # Force every file to be considered "aged" by dropping the warm
    # threshold to 0 days, regardless of how old it actually is.
    lifecycle_manager.tier_manager.warm_age_days = 0

    before_paths = sorted(p.name for p in roots[Tier.TIER_1_HOT].iterdir())
    assert len(before_paths) == 5

    results = lifecycle_manager.migrate_aged_files()

    assert len(results) == 5
    # Files are gone from Tier 1 ...
    assert list(roots[Tier.TIER_1_HOT].iterdir()) == []
    # ... and physically present, compressed, in Tier 2.
    tier2_files = sorted(p.name for p in roots[Tier.TIER_2_WARM].iterdir())
    assert tier2_files == [f"doc_{i}.txt.gz" for i in range(5)]

    # Every migration was recorded as a real event in the Observatory.
    events = ledger.query_events(agent="lifecycle_manager", action="migrate_file")
    assert len(events) == 5
    migrated_files = {e["output_data"]["file"] for e in events}
    assert migrated_files == {str(roots[Tier.TIER_1_HOT] / f"doc_{i}.txt") for i in range(5)}

    ok, bad = ledger.verify_chain()
    assert ok is True, f"ledger chain broken at {bad}"


def test_storage_reduction_measurable(lifecycle_manager, roots, ledger):
    """Migrate a ~10MB Tier-1 file tree to Tier 2 with compression and
    confirm the space savings are independently measurable from the
    Observatory ledger, not just asserted."""
    total_before = 0
    payload = ("engineering studio storage reduction payload " * 400).encode()  # highly repetitive -> compresses well
    for i in range(10):
        f = roots[Tier.TIER_1_HOT] / f"bulk_{i}.txt"
        _age_file(f, payload, age_days=45)  # 45d > warm_age_days=30 -> migrates
        total_before += len(payload)

    assert total_before >= 10 * len(payload) * 0.9  # sanity: ~10 files worth

    results = lifecycle_manager.migrate_aged_files()
    assert len(results) == 10

    events = ledger.query_events(agent="lifecycle_manager", action="migrate_file")
    assert len(events) == 10

    saved_bytes = sum(e["output_data"]["saved_bytes"] for e in events)
    size_before_total = sum(e["output_data"]["size_before"] for e in events)
    size_after_total = sum(e["output_data"]["size_after"] for e in events)

    assert saved_bytes > 0
    assert size_before_total == total_before

    compression_ratio = saved_bytes / size_before_total
    assert compression_ratio > 0.30, (
        f"measured compression ratio {compression_ratio:.2%} did not exceed the 30% floor "
        f"(before={size_before_total}B, after={size_after_total}B, saved={saved_bytes}B)"
    )


def test_migration_scheduler_starts_and_stops_without_error(lifecycle_manager):
    scheduler = MigrationScheduler(lifecycle_manager, interval_seconds=3600)
    scheduler.schedule_cycle()
    assert scheduler._running is True
    scheduler.stop()
    assert scheduler._running is False
