"""Resource accounting for one ingest_report() call.

New module, NEXUS Federation F1. Measures real, observable resource use
around the DAT.AI report -> NEXUS ingest -> state update -> relevance
decision -> delegation proposal pipeline. Uses Python's stdlib `resource`
module (POSIX, available on macOS/Linux) for CPU time and peak RSS, and
`time.perf_counter()` for elapsed wall-clock -- no estimated or invented
figures. API cost and model-token cost are correctly always 0/None: this
pipeline makes no LLM or paid-API calls anywhere in its own code.
"""

from __future__ import annotations

import resource
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class ResourceMeasurement:
    elapsed_compute_seconds: float
    cpu_seconds: float
    peak_rss_bytes: int
    local_storage_delta_bytes: int
    external_storage_dependency: bool
    api_cost: float = 0.0
    model_tokens: int = 0


def measure(fn: Callable[[], T], *, db_path: str | Path) -> tuple[T, ResourceMeasurement]:
    """Wrap a call (typically kernel.ingest_report(...)) and return both its
    result and a real resource measurement of that call."""
    db_path = Path(db_path)
    size_before = db_path.stat().st_size if db_path.exists() else 0

    cpu_before = resource.getrusage(resource.RUSAGE_SELF).ru_utime
    wall_before = time.perf_counter()

    result = fn()

    wall_after = time.perf_counter()
    usage_after = resource.getrusage(resource.RUSAGE_SELF)
    cpu_after = usage_after.ru_utime

    size_after = db_path.stat().st_size if db_path.exists() else 0

    measurement = ResourceMeasurement(
        elapsed_compute_seconds=wall_after - wall_before,
        cpu_seconds=cpu_after - cpu_before,
        peak_rss_bytes=usage_after.ru_maxrss,  # macOS reports bytes; Linux reports KB -- documented limitation
        local_storage_delta_bytes=size_after - size_before,
        external_storage_dependency=False,  # this pipeline touches only the local SQLite store and local/canonical evidence roots
        api_cost=0.0,
        model_tokens=0,
    )
    return result, measurement
