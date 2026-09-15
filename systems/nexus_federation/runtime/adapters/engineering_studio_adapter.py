"""F10B Stage 4: thin translation adapter for Engineering Studio.

Translates an EXISTING MeasuredExecutionResult (from
systems.engineering_studio.studio_v4.execution.measured_project_executor)
into a generic InstitutionalReport. Does NOT modify the executor's
behavior, does NOT grant it any new capability, and does NOT run any
mutation mission -- this phase's objective is bounded to A0/A1 observation.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

FEDERATION_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FEDERATION_ROOT))
sys.path.insert(0, str(FEDERATION_ROOT.parent))

from contracts.generic import (
    CapabilityLifecycle,
    CapabilityStatus,
    Confidence,
    OperatingState,
    build_report,
)


def build_report_from_measured_result(measured_result: Any, cycle_id: str) -> dict[str, Any]:
    """Translate a MeasuredExecutionResult into a generic InstitutionalReport
    payload dict. `measured_result` is whatever measured_project_executor.py's
    execute_test_cycle() returned -- untouched, not re-interpreted."""

    evidence_ref = f"engstudio_measured_result_{cycle_id}"

    report = build_report(
        institution="engineering_studio",
        mission_id="f10b-stage4-engstudio-shadow",
        objective="F10B Stage 4: bounded A0/A1 observation via existing measured test executor",
        operating_state=(
            OperatingState.INTEGRATED if measured_result.success else OperatingState.DEGRADED
        ),
        capability_statuses=[
            CapabilityStatus(
                name="measured_project_executor",
                lifecycle=CapabilityLifecycle.TESTED,
                confidence=Confidence(
                    value=0.85 if measured_result.success else 0.4,
                    basis=f"real subprocess test run, returncode captured, git_diff_stat observed",
                ),
                evidence_refs=[evidence_ref],
            )
        ],
        findings=[
            f"test_passed={measured_result.success}",
            f"git_diff_stat={measured_result.git_diff_stat!r}",
        ],
        evidence_refs=[evidence_ref],
        cycle_id=cycle_id,
    )
    return report.model_dump()
