#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


parser = argparse.ArgumentParser()

parser.add_argument(
    "--claim-map",
    required=True
)

parser.add_argument(
    "--output",
    required=True
)

args = parser.parse_args()

data = json.loads(
    Path(args.claim_map).read_text()
)

allowed = set(
    data.get(
        "allowed_validation_states",
        []
    )
)

results = []

for claim in data.get("claims", []):

    state = claim.get(
        "validation_state",
        "UNVERIFIED"
    )

    evidence = claim.get(
        "evidence_ids",
        []
    )

    disclosure = claim.get(
        "public_disclosure",
        "DENY"
    )

    eligible = (
        state in allowed
        and len(evidence) > 0
        and disclosure == "ALLOW"
    )

    reasons = []

    if state not in allowed:

        reasons.append(
            "VALIDATION_STATE_NOT_ALLOWED"
        )

    if not evidence:

        reasons.append(
            "NO_EVIDENCE"
        )

    if disclosure != "ALLOW":

        reasons.append(
            "DISCLOSURE_NOT_ALLOWED"
        )

    results.append({
        "claim_id":
            claim.get("claim_id"),

        "validation_state":
            state,

        "eligible":
            eligible,

        "reasons":
            reasons
    })


report = {
    "claim_count":
        len(results),

    "eligible_count":
        sum(
            1
            for x in results
            if x["eligible"]
        ),

    "claims":
        results
}


Path(args.output).write_text(
    json.dumps(
        report,
        indent=2
    ) + "\n"
)

print(
    json.dumps(
        {
            "claim_count":
                report["claim_count"],

            "eligible_count":
                report["eligible_count"]
        },
        indent=2
    )
)
