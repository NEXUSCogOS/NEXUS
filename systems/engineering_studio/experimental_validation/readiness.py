from __future__ import annotations

import json
from pathlib import Path

from .gate_validator import validate_gate_record


def evaluate_experiment(requirement, gate_records_dir):

    verified=[]
    unresolved=[]

    gate_records_dir=Path(gate_records_dir)

    for gate in requirement["required_gates"]:

        gate_id=gate["gate_id"]
        path=gate_records_dir/f"{gate_id}.json"

        canonical={
            "gate_id":gate_id,
            "canonical_gate_text":gate["gate"]
        }

        if not path.is_file():

            unresolved.append({
                "gate_id":gate_id,
                "reason":"FORMAL_GATE_RECORD_MISSING"
            })

            continue

        result=validate_gate_record(path,canonical)

        if result["valid"]:
            verified.append(gate_id)

        else:
            unresolved.append({
                "gate_id":gate_id,
                "reason":"FORMAL_GATE_RECORD_INVALID",
                "validation_reasons":result["reasons"]
            })

    all_verified=(
        len(unresolved)==0
        and
        len(verified)==requirement["required_gate_count"]
    )

    status=requirement["registry_status"]

    if all_verified and status=="READY":
        authorization="READY"

    elif all_verified:
        authorization="READY_ELIGIBLE"

    else:
        authorization="BLOCKED"

    return {
        "experiment_id":requirement["experiment_id"],
        "registry_status":status,
        "required_gate_count":requirement["required_gate_count"],
        "verified_gate_count":len(verified),
        "unresolved_gate_count":len(unresolved),
        "verified_gate_ids":verified,
        "unresolved":unresolved,
        "all_required_gates_verified":all_verified,
        "authorization":authorization,
        "registry_transition_performed":False,
        "execution_authorized":authorization=="READY"
    }


def evaluate_all(requirements_file,gate_records_dir):

    requirements=json.loads(
        Path(requirements_file).read_text()
    )

    return [
        evaluate_experiment(x,gate_records_dir)
        for x in requirements
    ]
