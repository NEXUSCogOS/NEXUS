#!/usr/bin/env python3

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    h = hashlib.sha256()

    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)

    return h.hexdigest()


parser = argparse.ArgumentParser()

parser.add_argument(
    "--registry",
    required=True
)

parser.add_argument(
    "--output",
    required=True
)

args = parser.parse_args()

registry_path = Path(args.registry)

data = json.loads(
    registry_path.read_text()
)

report = {
    "generated_at":
        datetime.now(timezone.utc).isoformat(),

    "artifacts": []
}

for artifact in data.get("artifacts", []):

    source = Path(
        artifact.get("source_path", "")
    )

    previous = artifact.get(
        "source_sha256"
    )

    entry = {
        "artifact_id":
            artifact.get("artifact_id"),

        "source_path":
            str(source),

        "previous_sha256":
            previous,

        "current_sha256":
            None,

        "state":
            "UNKNOWN"
    }

    if not source.exists():

        entry["state"] = "SOURCE_MISSING"

    elif not source.is_file():

        entry["state"] = "SOURCE_NOT_FILE"

    else:

        current = digest(source)

        entry["current_sha256"] = current

        if previous is None:

            entry["state"] = "UNBASELINED"

        elif current == previous:

            entry["state"] = "CURRENT"

        else:

            entry["state"] = "STALE"

    report["artifacts"].append(entry)


Path(args.output).write_text(
    json.dumps(
        report,
        indent=2
    ) + "\n"
)

states = {}

for item in report["artifacts"]:

    state = item["state"]

    states[state] = (
        states.get(state, 0) + 1
    )

print(
    json.dumps(
        {
            "artifact_count":
                len(report["artifacts"]),

            "states":
                states
        },
        indent=2
    )
)
