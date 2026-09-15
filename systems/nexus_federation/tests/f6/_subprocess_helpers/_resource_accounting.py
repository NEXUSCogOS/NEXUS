"""Real, measured resource accounting for F6 subprocesses (mission
section 19: "Do not estimate unmeasured fields").

Only CPU time (user+sys) and peak RSS are measured -- both available from
`resource.getrusage(RUSAGE_SELF)` on every process, unconditionally, with
no instrumentation gaps. Elapsed wall-clock time is measured directly by
this process via `time.monotonic()`. Local storage delta, external
storage activity, API call count, API cost, and model token usage are
NOT measured anywhere in this F6 harness -- each subprocess reports them
explicitly as null/UNMEASURED rather than omitting the field silently or
estimating a plausible-looking number.

Usage (no reindentation of existing code required):
    meter = ResourceMeter()
    meter.start()
    ... existing function body, unchanged ...
    result = {... , "resource_usage": meter.stop()}
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
        # ru_maxrss is a high-water mark for the whole process, not a
        # delta -- reporting the END value is the closest honest
        # measurement available; these are single-purpose, short-lived
        # subprocesses that do nothing else before start() is called.
        return {
            "cpu_seconds": round(cpu_seconds, 6),
            "peak_rss_bytes": end_rusage.ru_maxrss,
            "elapsed_seconds": round(end_wall - self._start_wall, 6),
            "local_storage_delta_bytes": None,   # UNMEASURED
            "external_storage_activity": None,   # UNMEASURED
            "api_calls": None,                   # UNMEASURED
            "api_cost_usd": None,                # UNMEASURED
            "model_tokens": None,                # UNMEASURED -- no LLM call in this harness
        }
