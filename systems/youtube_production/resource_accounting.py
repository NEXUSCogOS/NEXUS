"""Real, measured resource accounting for F8 subprocesses (mission
section 32: unknown remains UNKNOWN, never estimated). Same discipline
and shape as F6/F7's own `_resource_accounting.ResourceMeter` -- kept as
a small, importable, package-level module here rather than a test-only
helper, since production.py itself (not just tests) needs it.
"""

from __future__ import annotations

import resource
import time


class ResourceMeter:
    def start(self) -> "ResourceMeter":
        self._start_wall = time.monotonic()
        self._start_rusage = resource.getrusage(resource.RUSAGE_SELF)
        return self

    def stop(self) -> dict:
        end_wall = time.monotonic()
        end_rusage = resource.getrusage(resource.RUSAGE_SELF)
        cpu_seconds = (
            (end_rusage.ru_utime - self._start_rusage.ru_utime)
            + (end_rusage.ru_stime - self._start_rusage.ru_stime)
        )
        return {
            "cpu_seconds": round(cpu_seconds, 6),
            "peak_rss_bytes": end_rusage.ru_maxrss,
            "elapsed_seconds": round(end_wall - self._start_wall, 6),
            "local_storage_delta_bytes": None,   # UNMEASURED
            "api_calls": 0,                       # no external API is ever called by this package
            "api_cost_usd": 0.0,
            "model_tokens": 0,                    # no LLM call in this package's script/render path
        }
