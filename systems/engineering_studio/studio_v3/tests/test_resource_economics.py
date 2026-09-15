"""Tests for the Resource Economics Engine (real, measured metrics).

All tests use tmp_path fixtures — never the real 67k-file
.directives-ingestion directory, which belongs in a separate manual /
integration script, not the fast unit suite.
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from observatory.resource_economics import (
    ResourceMeter,
    measure_directive_backlog,
    measure_storage_delta,
)


def test_resource_meter_wall_seconds_measures_real_sleep():
    with ResourceMeter(label="sleep_block") as meter:
        time.sleep(0.05)

    result = meter.result
    assert result["label"] == "sleep_block"
    assert result["wall_seconds"] > 0.04
    assert "start_timestamp" in result
    assert "end_timestamp" in result
    assert result["process_lifetime_peak_rss_kb"] > 0


def test_resource_meter_cpu_seconds_measures_real_cpu_work():
    with ResourceMeter(label="cpu_block") as meter:
        total = 0
        for i in range(10_000_000):
            total += i

    result = meter.result
    assert result["cpu_seconds"] > 0
    assert result["label"] == "cpu_block"


def test_process_lifetime_peak_rss_kb_is_monotonic_nondecreasing():
    """process_lifetime_peak_rss_kb reflects ru_maxrss, which is the peak
    RSS over the *entire process lifetime*, not a per-block measurement.
    Successive ResourceMeter readings within the same process must
    therefore never decrease, even if the second block does less work or
    frees memory — the OS-reported high-water mark only ever goes up.
    """
    with ResourceMeter(label="first_block") as meter_one:
        _ = bytearray(10_000_000)  # allocate ~10MB to push the high-water mark up

    first_peak = meter_one.result["process_lifetime_peak_rss_kb"]

    with ResourceMeter(label="second_block") as meter_two:
        pass  # do nothing; peak must not drop below first_peak

    second_peak = meter_two.result["process_lifetime_peak_rss_kb"]

    assert second_peak >= first_peak


def test_measure_storage_delta_on_file_of_known_size(tmp_path):
    f = tmp_path / "known.bin"
    n_bytes = 12345
    f.write_bytes(b"x" * n_bytes)

    result = measure_storage_delta(f)

    assert result["size_bytes"] == n_bytes
    assert result["path"] == str(f)
    assert "measured_at" in result


def test_measure_storage_delta_on_directory_sums_known_files(tmp_path):
    d = tmp_path / "some_dir"
    d.mkdir()
    (d / "a.bin").write_bytes(b"a" * 1000)
    (d / "b.bin").write_bytes(b"b" * 2500)
    sub = d / "nested"
    sub.mkdir()
    (sub / "c.bin").write_bytes(b"c" * 500)

    result = measure_storage_delta(d)

    assert result["size_bytes"] == 1000 + 2500 + 500
    assert result["path"] == str(d)


def test_measure_directive_backlog_counts_per_subdir(tmp_path):
    root = tmp_path / ".directives-ingestion"
    root.mkdir()
    for name in ["pending", "approved", "in-progress", "completed", "rejected"]:
        (root / name).mkdir()

    # pending: 3 files
    (root / "pending" / "d1.md").write_bytes(b"1" * 100)
    (root / "pending" / "d2.md").write_bytes(b"2" * 200)
    (root / "pending" / "d3.md").write_bytes(b"3" * 300)

    # approved: 1 file
    (root / "approved" / "a1.md").write_bytes(b"a" * 50)

    # in-progress, completed, rejected: empty

    result = measure_directive_backlog(root)

    assert result["subdirs"]["pending"]["file_count"] == 3
    assert result["subdirs"]["pending"]["total_bytes"] == 600
    assert result["subdirs"]["approved"]["file_count"] == 1
    assert result["subdirs"]["approved"]["total_bytes"] == 50
    assert result["subdirs"]["in-progress"]["file_count"] == 0
    assert result["subdirs"]["completed"]["file_count"] == 0
    assert result["subdirs"]["rejected"]["file_count"] == 0
    assert result["directives_root"] == str(root)
