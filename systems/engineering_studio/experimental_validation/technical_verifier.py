from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path


TECHNICAL_GATES = {
    "global-03":
        "clean-environment build or environment lock reproduced",

    "global-04":
        "research data physically or logically isolated from production writers",

    "global-05":
        "backup integrity verified and at least one restore rehearsal passed",

    "global-06":
        "monitoring detects a deliberately injected non-destructive failure",

    "NEXUS-EXP-001-04":
        "corpus and event log restore tested",

    "NEXUS-EXP-002-03":
        "restore rehearsal passed",

    "NEXUS-EXP-002-04":
        "test store demonstrably isolated",

    "NEXUS-EXP-005-01":
        "tested restore",

    "NEXUS-EXP-005-04":
        "disk headroom safe",

    "NEXUS-EXP-006-04":
        "clean environment available",
}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def result(gate_id, status, check, **kwargs):
    return {
        "gate_id": gate_id,
        "canonical_gate_text":
            TECHNICAL_GATES[gate_id],
        "status": status,
        "check": check,
        "observed_at": utcnow(),
        "formal_gate_pass_created": False,
        **kwargs,
    }


def verify_disk_headroom(gate_id, root):
    usage = shutil.disk_usage(root)

    free_fraction = (
        usage.free / usage.total
        if usage.total else 0
    )

    # Observation only. Canonical policy must define
    # what fraction constitutes "safe".
    return result(
        gate_id,
        "OBSERVED",
        "disk_headroom",
        total_bytes=usage.total,
        used_bytes=usage.used,
        free_bytes=usage.free,
        free_fraction=free_fraction,
        reason=(
            "Disk state measured. No PASS inferred "
            "without an authoritative safety threshold."
        ),
    )


def verify_clean_environment(gate_id, root):
    candidates = []

    for name in (
        "requirements.txt",
        "requirements.lock",
        "poetry.lock",
        "uv.lock",
        "Pipfile.lock",
        "pyproject.toml",
        "environment.yml",
    ):
        p = root / name
        if p.is_file():
            candidates.append(str(p))

    return result(
        gate_id,
        "HUMAN_REVIEW_REQUIRED",
        "clean_environment",
        environment_definition_candidates=candidates,
        reason=(
            "Presence of an environment definition does "
            "not prove clean-environment reproduction. "
            "A separate isolated reproduction is required."
        ),
    )


def verify_restore(gate_id, root):
    return result(
        gate_id,
        "HUMAN_REVIEW_REQUIRED",
        "restore_rehearsal",
        reason=(
            "Restore PASS requires an actual isolated "
            "restore rehearsal with source hash, backup "
            "hash, restored hash, timestamps and outcome. "
            "Commissioning will not mutate or restore live data."
        ),
    )


def verify_isolation(gate_id, root):
    return result(
        gate_id,
        "HUMAN_REVIEW_REQUIRED",
        "writer_isolation",
        reason=(
            "Configuration text alone cannot prove isolation. "
            "Verification requires scoped writer/process/open-handle "
            "evidence against the actual research store."
        ),
    )


def verify_failure_injection(gate_id, root):
    return result(
        gate_id,
        "NOT_TESTABLE_DURING_COMMISSIONING",
        "monitoring_failure_injection",
        reason=(
            "A deliberate failure will not be injected by "
            "the package installer. Run only through a separately "
            "authorized non-destructive test procedure."
        ),
    )


def verify(gate_id: str, nexus_root: str):
    if gate_id not in TECHNICAL_GATES:
        return {
            "gate_id": gate_id,
            "status": "NOT_TECHNICAL_GATE",
            "formal_gate_pass_created": False,
        }

    root = Path(nexus_root).resolve()

    if not root.is_dir():
        return result(
            gate_id,
            "FAIL",
            "root_validation",
            reason=f"NEXUS root missing: {root}",
        )

    if gate_id == "NEXUS-EXP-005-04":
        return verify_disk_headroom(
            gate_id, root
        )

    if gate_id in {
        "global-03",
        "NEXUS-EXP-006-04",
    }:
        return verify_clean_environment(
            gate_id, root
        )

    if gate_id in {
        "global-05",
        "NEXUS-EXP-001-04",
        "NEXUS-EXP-002-03",
        "NEXUS-EXP-005-01",
    }:
        return verify_restore(
            gate_id, root
        )

    if gate_id in {
        "global-04",
        "NEXUS-EXP-002-04",
    }:
        return verify_isolation(
            gate_id, root
        )

    if gate_id == "global-06":
        return verify_failure_injection(
            gate_id, root
        )

    return result(
        gate_id,
        "NOT_TESTABLE",
        "unmapped",
    )


def verify_all(nexus_root: str):
    return [
        verify(gid, nexus_root)
        for gid in sorted(TECHNICAL_GATES)
    ]
