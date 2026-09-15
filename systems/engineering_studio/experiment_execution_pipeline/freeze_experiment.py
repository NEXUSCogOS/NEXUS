from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime,timezone
from pathlib import Path


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def main():

    if len(sys.argv)!=5:
        raise SystemExit(
            "usage: freeze_experiment.py "
            "REGISTRY REQUIREMENTS GATE_RECORDS OUTPUT"
        )

    registry=Path(sys.argv[1])
    requirements=Path(sys.argv[2])
    gates=Path(sys.argv[3])
    out=Path(sys.argv[4])

    out.mkdir(parents=True,exist_ok=False)

    reg=json.loads(registry.read_text())
    req=json.loads(requirements.read_text())

    experiment_id=out.name

    experiment=next(
        x for x in reg["experiments"]
        if x["experiment_id"]==experiment_id
    )

    requirement=next(
        x for x in req
        if x["experiment_id"]==experiment_id
    )

    gate_dir=out/"gate_records"
    gate_dir.mkdir()

    gate_hashes={}

    for gate in requirement["required_gates"]:

        gid=gate["gate_id"]
        src=gates/f"{gid}.json"

        if not src.is_file():
            raise SystemExit(
                f"gate missing: {gid}"
            )

        dst=gate_dir/src.name
        shutil.copy2(src,dst)

        gate_hashes[gid]=sha(dst)

    (out/"EXPERIMENT_RECORD.json").write_text(
        json.dumps(experiment,indent=2)+"\n"
    )

    (out/"REQUIREMENTS.json").write_text(
        json.dumps(requirement,indent=2)+"\n"
    )

    manifest={
        "experiment_id":experiment_id,
        "frozen_at":
            datetime.now(timezone.utc).isoformat(),

        "registry_sha256":
            sha(registry),

        "experiment_record_sha256":
            sha(out/"EXPERIMENT_RECORD.json"),

        "requirements_sha256":
            sha(out/"REQUIREMENTS.json"),

        "gate_record_sha256":
            gate_hashes,

        "post_freeze_mutation":
            "PROHIBITED"
    }

    (out/"FREEZE_MANIFEST.json").write_text(
        json.dumps(manifest,indent=2)+"\n"
    )

    print(
        json.dumps(manifest,indent=2)
    )


if __name__=="__main__":
    main()
