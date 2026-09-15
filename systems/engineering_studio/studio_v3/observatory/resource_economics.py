"""Resource Economics Engine — real, measured resource consumption.

Every value produced here is a real measurement taken via OS/process
syscalls (time.perf_counter, time.process_time, resource.getrusage,
os.stat / os.walk / os.scandir). Nothing is estimated, guessed, or
hardcoded. This is deliberate: Engineering Studio v3 was found to
fabricate metrics (constant values regardless of real work), and this
module exists to be the opposite of that.
"""

from __future__ import annotations

import os
import resource
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]


def _utc_iso_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


class ResourceMeter:
    """Context manager that measures real resource consumption for a block.

    Usage:
        with ResourceMeter(label="some_operation") as meter:
            ... do work ...
        result = meter.result  # populated after __exit__
    """

    def __init__(self, label: str):
        self.label = label
        self.result: dict | None = None
        self._wall_start: float | None = None
        self._cpu_start: float | None = None
        self._start_timestamp: str | None = None

    def __enter__(self) -> "ResourceMeter":
        self._start_timestamp = _utc_iso_now()
        # perf_counter: highest-resolution monotonic wall clock available.
        self._wall_start = time.perf_counter()
        # process_time: this process's CPU time (user + system), NOT wall
        # clock — it will read lower than wall_seconds under I/O wait, and
        # can differ from wall clock in either direction under threading.
        self._cpu_start = time.process_time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        wall_end = time.perf_counter()
        cpu_end = time.process_time()
        end_timestamp = _utc_iso_now()

        wall_seconds = wall_end - self._wall_start
        cpu_seconds = cpu_end - self._cpu_start

        # ru_maxrss cross-platform gotcha:
        # - On Linux, ru_maxrss is reported in KILOBYTES (per getrusage(2)).
        # - On macOS (BSD/Darwin libc), ru_maxrss is reported in BYTES, not
        #   kilobytes, despite the man page family being shared with Linux.
        #   This is a well-known, frequently-mis-ported cross-platform bug
        #   source (e.g. Python's own resource module docs gloss over it).
        #   We detect the platform explicitly and normalize to KB uniformly
        #   so process_lifetime_peak_rss_kb means the same thing on every platform.
        raw_maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            process_lifetime_peak_rss_kb = int(raw_maxrss / 1024)
        else:
            process_lifetime_peak_rss_kb = int(raw_maxrss)

        self.result = {
            "label": self.label,
            "wall_seconds": wall_seconds,
            "cpu_seconds": cpu_seconds,
            "process_lifetime_peak_rss_kb": process_lifetime_peak_rss_kb,
            "start_timestamp": self._start_timestamp,
            "end_timestamp": end_timestamp,
        }


def measure_storage_delta(path: PathLike) -> dict:
    """Measure the real on-disk size of a file or directory right now.

    For a file, uses os.stat. For a directory, performs a real recursive
    walk-and-sum via os.walk + os.path.getsize. This does not diff anything
    itself — call it twice (before/after) and diff `size_bytes` yourself.
    """
    p = Path(path)

    if p.is_file():
        size_bytes = os.stat(p).st_size
    elif p.is_dir():
        total = 0
        for dirpath, _dirnames, filenames in os.walk(p):
            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                try:
                    total += os.path.getsize(fpath)
                except OSError:
                    # File vanished (race) or broken symlink — skip it
                    # rather than fabricate a value.
                    continue
        size_bytes = total
    else:
        raise FileNotFoundError(f"No such file or directory: {p}")

    return {
        "path": str(p),
        "size_bytes": size_bytes,
        "measured_at": _utc_iso_now(),
    }


def measure_directive_backlog(directives_root: PathLike) -> dict:
    """Measure real counts/bytes per subdir of a .directives-ingestion tree.

    Expects subdirs: pending/, approved/, in-progress/, completed/, rejected/.
    Uses real os.scandir / os.stat calls — no estimation. Missing subdirs
    are reported with zero counts/bytes rather than raising, since not every
    directives tree will have all five populated.
    """
    root = Path(directives_root)
    subdirs = ["pending", "approved", "in-progress", "completed", "rejected"]

    counts: dict[str, dict] = {}
    for name in subdirs:
        subdir_path = root / name
        file_count = 0
        total_bytes = 0

        if subdir_path.is_dir():
            with os.scandir(subdir_path) as it:
                for entry in it:
                    if entry.is_file(follow_symlinks=False):
                        file_count += 1
                        try:
                            total_bytes += entry.stat(follow_symlinks=False).st_size
                        except OSError:
                            continue

        counts[name] = {
            "file_count": file_count,
            "total_bytes": total_bytes,
        }

    return {
        "directives_root": str(root),
        "subdirs": counts,
        "measured_at": _utc_iso_now(),
    }
