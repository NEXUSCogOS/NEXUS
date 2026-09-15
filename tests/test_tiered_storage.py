"""Tests for TierManager (classification + tier configuration)."""

from __future__ import annotations

import os
import time

import pytest

from systems.engineering_studio.studio_v4.storage.tiered_storage import (
    FileDescriptor,
    Tier,
    TierManager,
)


@pytest.fixture
def tier_manager(tmp_path):
    roots = {
        Tier.TIER_1_HOT: tmp_path / "tier1",
        Tier.TIER_2_WARM: tmp_path / "tier2",
        Tier.TIER_3_COLD: tmp_path / "tier3",
    }
    for p in roots.values():
        p.mkdir(parents=True, exist_ok=True)
    return TierManager(tier_roots=roots, warm_age_days=30, cold_age_days=90, large_file_bytes=1024)


def _make_file(path, size_bytes: int, age_days: float) -> FileDescriptor:
    path.write_bytes(b"x" * size_bytes)
    old_time = time.time() - (age_days * 86400)
    os.utime(path, (old_time, old_time))
    return FileDescriptor.from_path(path)


def test_get_tier_config_returns_correct_roots(tier_manager, tmp_path):
    cfg1 = tier_manager.get_tier_config(Tier.TIER_1_HOT)
    cfg2 = tier_manager.get_tier_config(Tier.TIER_2_WARM)
    cfg3 = tier_manager.get_tier_config(Tier.TIER_3_COLD)

    assert cfg1.root_path == tmp_path / "tier1"
    assert cfg2.root_path == tmp_path / "tier2"
    assert cfg3.root_path == tmp_path / "tier3"
    assert cfg1.compress is False
    assert cfg2.compress is True
    assert cfg3.compress is True


def test_classify_fresh_small_file_is_tier1(tier_manager, tmp_path):
    fd = _make_file(tmp_path / "tier1" / "fresh.txt", size_bytes=10, age_days=1)
    assert tier_manager.classify_file(fd) == Tier.TIER_1_HOT


def test_classify_aged_file_is_tier2(tier_manager, tmp_path):
    fd = _make_file(tmp_path / "tier1" / "aged.txt", size_bytes=10, age_days=45)
    assert tier_manager.classify_file(fd) == Tier.TIER_2_WARM


def test_classify_very_aged_file_is_tier3(tier_manager, tmp_path):
    fd = _make_file(tmp_path / "tier1" / "old.txt", size_bytes=10, age_days=120)
    assert tier_manager.classify_file(fd) == Tier.TIER_3_COLD


def test_classify_large_fresh_file_bumped_to_tier2(tier_manager, tmp_path):
    fd = _make_file(tmp_path / "tier1" / "big.bin", size_bytes=2048, age_days=1)
    assert tier_manager.classify_file(fd) == Tier.TIER_2_WARM


def test_should_migrate_true_when_classification_forward(tier_manager, tmp_path):
    fd = _make_file(tmp_path / "tier1" / "aged.txt", size_bytes=10, age_days=45)
    assert tier_manager.should_migrate(fd) is True


def test_should_migrate_false_when_already_in_target_tier(tier_manager, tmp_path):
    fd = _make_file(tmp_path / "tier1" / "aged.txt", size_bytes=10, age_days=45)
    fd.current_tier = Tier.TIER_2_WARM
    assert tier_manager.should_migrate(fd) is False


def test_should_migrate_never_recommends_backward_migration(tier_manager, tmp_path):
    fd = _make_file(tmp_path / "tier1" / "fresh.txt", size_bytes=10, age_days=1)
    fd.current_tier = Tier.TIER_3_COLD
    assert tier_manager.should_migrate(fd) is False


def test_file_descriptor_age_days_matches_real_mtime(tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("hello")
    old_time = time.time() - (5 * 86400)
    os.utime(p, (old_time, old_time))
    fd = FileDescriptor.from_path(p)
    assert 4.9 <= fd.age_days <= 5.1


def test_target_path_for_preserves_relative_structure(tier_manager, tmp_path):
    subdir = tmp_path / "tier1" / "sub" / "dir"
    subdir.mkdir(parents=True)
    fd = _make_file(subdir / "nested.txt", size_bytes=10, age_days=1)
    target = tier_manager.target_path_for(fd, Tier.TIER_2_WARM)
    assert target == tmp_path / "tier2" / "sub" / "dir" / "nested.txt"
