from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.home() / "NEXUS"
ES = ROOT / "systems" / "engineering_studio"
EV = ES / "experimental_validation"
PIPE = ES / "experiment_execution_pipeline"
REG = ROOT / "systems" / "librarian" / "experiments" / "registry.json"
REQ = EV / "config" / "experiment_requirements.json"
HERE = Path(__file__).resolve().parent

CONFIG = json.loads(
    (HERE / "config" / "programme.json").read_text()
)

sys.path.insert(0, str(ES))

from experimental_validation.readiness import evaluate_all
from experimental_validation.gate_validator import validate_gate_record


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n")


def verify_formal_store():

    requirements = load(REQ)

    canonical = {}

    for exp in requirements:
        for gate in exp["required_gates"]:
            canonical[gate["gate_id"]] = gate["gate"]

    valid = []

    for path in sorted((EV / "gate_records").glob("*.json")):

        gid = path.stem

        if gid not in canonical:
            continue

        result = validate_gate_record(
            path,
            {
                "gate_id": gid,
                "canonical_gate_text": canonical[gid],
            },
        )

        if not result["valid"]:
            raise RuntimeError(
                f"INVALID_FORMAL_GATE:{gid}:{result['reasons']}"
            )

        valid.append(gid)

    return valid


def readiness():

    return evaluate_all(
        REQ,
        EV / "gate_records",
    )


def registry_record(expid):

    registry = load(REG)

    return next(
        x for x in registry["experiments"]
        if x["experiment_id"] == expid
    )


def governance(expid):

    state = next(
        x for x in readiness()
        if x["experiment_id"] == expid
    )

    record = registry_record(expid)

    reasons = []

    if not state["all_required_gates_verified"]:
        reasons.append("GATES_INCOMPLETE")

    if state["authorization"] != "READY":
        reasons.append("READINESS_NOT_READY")

    if record["result_status"] != "READY":
        reasons.append("REGISTRY_NOT_READY")

    return {
        "experiment_id": expid,
        "allowed": not reasons,
        "reasons": reasons,
        "readiness": state,
        "registry_status": record["result_status"],
    }


def freeze(expid, run_root):

    destination = run_root / "freeze" / expid

    result = subprocess.run(
        [
            sys.executable,
            str(PIPE / "freeze_experiment.py"),
            str(REG),
            str(REQ),
            str(EV / "gate_records"),
            str(destination),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "FREEZE_FAILED\n"
            + result.stdout
            + result.stderr
        )

    return destination


def runner_candidates():

    return [
        ES / "studio_v5" / "research_evolution" /
        "experiments" / "experiment_runner.py",

        ES / "studio_v3" / "execution" /
        "test_runner.py",
    ]


def bind_runner():

    for runner in runner_candidates():

        if not runner.is_file():
            continue

        probe = subprocess.run(
            [sys.executable, str(runner), "--help"],
            capture_output=True,
            text=True,
        )

        text = (
            probe.stdout + probe.stderr
        ).lower()

        if (
            "experiment" in text
            and
            "output" in text
        ):
            return runner

    return None


def main():

    formal = verify_formal_store()
    rows = readiness()

    status = {
        "programme_id": CONFIG["programme_id"],
        "checked_at": utc(),
        "formal_store_valid": True,
        "formal_record_count": len(formal),
        "readiness": rows,
        "registry_sha256": sha(REG),
        "registry_transition_performed": False,
        "experiment_execution_performed": False,
        "github_action_performed": False,
    }

    executable = [
        r["experiment_id"]
        for r in rows
        if r["execution_authorized"]
    ]

    if not executable:

        status["status"] = "HUMAN_REVIEW_PENDING"

        save(
            HERE / "state" / "STATUS.json",
            status,
        )

        print(json.dumps(status, indent=2))
        return 0

    runner = bind_runner()

    if runner is None:

        status["status"] = "RUNNER_BINDING_REQUIRED"

        save(
            HERE / "state" / "STATUS.json",
            status,
        )

        print(json.dumps(status, indent=2))
        return 20

    stamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%SZ")

    run_root = (
        HERE /
        "runs" /
        f"PROGRAMME_{stamp}"
    )

    run_root.mkdir(parents=True)

    for expid in CONFIG["execution_order"]:

        check = governance(expid)

        if not check["allowed"]:

            save(
                run_root / "GOVERNANCE_STOP.json",
                check,
            )

            print(
                f"STOP {expid}: "
                + ",".join(check["reasons"])
            )

            return 30

        frozen = freeze(expid, run_root)

        #
        # Deliberate final boundary:
        #
        # The orchestration layer freezes the eligible
        # experiment but does not guess the runner's
        # experiment-specific invocation contract.
        #
        # Actual execution requires an explicitly
        # commissioned canonical runner adapter.
        #

        save(
            run_root /
            f"{expid}_EXECUTION_HANDOFF.json",
            {
                "experiment_id": expid,
                "frozen_at": utc(),
                "freeze_root": str(frozen.resolve()),
                "runner": str(runner.resolve()),
                "execution_started": False,
                "status": "CANONICAL_RUNNER_HANDOFF",
            },
        )

        print(
            f"{expid}: FROZEN → CANONICAL_RUNNER_HANDOFF"
        )

        return 40

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
