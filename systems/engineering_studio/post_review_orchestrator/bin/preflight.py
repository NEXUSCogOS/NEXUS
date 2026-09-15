#!/usr/bin/env python3

import hashlib
import json
import sys
from pathlib import Path

ROOT=Path.home()/"NEXUS"
ES=ROOT/"systems/engineering_studio"
EV=ES/"experimental_validation"

sys.path.insert(0,str(ES))

from experimental_validation.gate_validator import validate_gate_record
from experimental_validation.readiness import evaluate_all

requirements=json.loads(
    (EV/"config/experiment_requirements.json").read_text()
)

canonical={}

for exp in requirements:
    for gate in exp["required_gates"]:
        canonical[gate["gate_id"]]=gate["gate"]

invalid=[]

for p in sorted((EV/"gate_records").glob("*.json")):

    gid=p.stem

    if gid not in canonical:
        continue

    r=validate_gate_record(
        p,
        {
            "gate_id":gid,
            "canonical_gate_text":canonical[gid]
        }
    )

    if not r["valid"]:
        invalid.append({
            "gate_id":gid,
            "reasons":r["reasons"]
        })

if invalid:
    print(json.dumps({
        "status":"FAIL",
        "invalid_records":invalid
    },indent=2))
    raise SystemExit(20)

rows=evaluate_all(
    EV/"config/experiment_requirements.json",
    EV/"gate_records"
)

primary=[
    x for x in rows
    if x["experiment_id"]!="NEXUS-EXP-006"
]

ready_eligible=[
    x["experiment_id"]
    for x in primary
    if x["authorization"]=="READY_ELIGIBLE"
]

ready=[
    x["experiment_id"]
    for x in primary
    if x["authorization"]=="READY"
]

blocked=[
    {
        "experiment_id":x["experiment_id"],
        "verified":
            x["verified_gate_count"],
        "required":
            x["required_gate_count"],
        "unresolved":
            x["unresolved"]
    }
    for x in primary
    if x["authorization"]=="BLOCKED"
]

result={
    "status":
        "HUMAN_REVIEW_PENDING"
        if blocked
        else "POST_REVIEW_ELIGIBLE",

    "formal_store_valid":True,

    "ready_eligible":
        ready_eligible,

    "ready":
        ready,

    "blocked":
        blocked,

    "execution_authorized":
        bool(ready),

    "registry_transition_performed":
        False,

    "experiment_execution_performed":
        False
}

print(json.dumps(result,indent=2))

if blocked:
    raise SystemExit(10)
