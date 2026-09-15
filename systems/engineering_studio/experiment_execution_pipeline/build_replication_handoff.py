from __future__ import annotations

import json
import sys
from datetime import datetime,timezone
from pathlib import Path


def main():

    if len(sys.argv)!=4:
        raise SystemExit(
            "usage: build_replication_handoff.py "
            "EXPERIMENT_ID SEALED_BUNDLE OUTPUT"
        )

    experiment_id=sys.argv[1]
    bundle=Path(sys.argv[2])
    output=Path(sys.argv[3])

    seal=bundle/"SEAL.json"

    if not seal.is_file():
        raise SystemExit(
            "FAIL: predecessor evidence not sealed"
        )

    s=json.loads(seal.read_text())

    if s.get("sealed") is not True:
        raise SystemExit(
            "FAIL: invalid predecessor seal"
        )

    handoff={
        "original_experiment":
            experiment_id,

        "created_at":
            datetime.now(timezone.utc).isoformat(),

        "sealed_bundle":
            str(bundle.resolve()),

        "sealed_bundle_manifest_sha256":
            s["manifest_sha256"],

        "independent_replicator":
            "PENDING",

        "clean_environment":
            "PENDING",

        "EXP006_execution_authorized":
            False
    }

    output.write_text(
        json.dumps(handoff,indent=2)+"\n"
    )

    print(json.dumps(handoff,indent=2))


if __name__=="__main__":
    main()
