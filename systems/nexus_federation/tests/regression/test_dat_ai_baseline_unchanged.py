"""REGRESSION test: DAT.AI's own canonical test suite must be unaffected by
the existence of the NEXUS federation substrate.

This test invokes DAT.AI's real pytest suite as a subprocess (DAT.AI has
its own venv, its own DATABASE_URL requirement, and its own pytest.ini --
it cannot be collected in-process alongside nexus_federation's tests
without conflating two different runtime environments). It is skipped
automatically when DAT.AI's test prerequisites (its venv, a reachable
PostGIS instance) are not present in the current environment, so it never
produces a false failure in an environment that simply hasn't set those up
-- but when it runs, it must reproduce the known baseline exactly.
"""

from __future__ import annotations

import os
import subprocess

import pytest

DAT_AI_VENV_PYTHON = "/Volumes/NEXUS/NEXUS_LOCAL/systems/dat_ai/.venv/bin/python3"
DAT_AI_CANONICAL = "${NEXUS_ROOT}/systems/dat_ai"

KNOWN_BASELINE = {
    "passed": 130,
    "failed": 1,  # pre-existing, diagnosed, out-of-scope (test_against_real_postgis)
    "skipped": 3,  # documented, Phase D scope
}


def _dat_ai_prerequisites_available() -> bool:
    if not os.path.exists(DAT_AI_VENV_PYTHON):
        return False
    if "DATABASE_URL" not in os.environ:
        return False
    return True


@pytest.mark.skipif(
    not _dat_ai_prerequisites_available(),
    reason="DAT.AI's own venv and a live DATABASE_URL are required to run its canonical suite",
)
def test_dat_ai_canonical_suite_unchanged():
    result = subprocess.run(
        [DAT_AI_VENV_PYTHON, "-m", "pytest", "-q", "--no-header"],
        cwd=DAT_AI_CANONICAL,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PYTHONPATH": DAT_AI_CANONICAL,
            "DAT_AI_RUNTIME_MODE": "test",
        },
        timeout=120,
    )
    output = result.stdout + result.stderr
    last_line = [l for l in output.splitlines() if l.strip()][-1]

    assert f"{KNOWN_BASELINE['passed']} passed" in last_line, last_line
    assert f"{KNOWN_BASELINE['failed']} failed" in last_line, last_line
    assert f"{KNOWN_BASELINE['skipped']} skipped" in last_line, last_line
