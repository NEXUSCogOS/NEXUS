from __future__ import annotations

import json
import sys
from pathlib import Path


def main():

    if len(sys.argv)!=4:
        raise SystemExit(
            "usage: score_result.py "
            "FREEZE RESULTS OUTPUT"
        )

    freeze=Path(sys.argv[1])
    results=Path(sys.argv[2])
    output=Path(sys.argv[3])

    experiment=json.loads(
        (freeze/"EXPERIMENT_RECORD.json").read_text()
    )

    actual=json.loads(
        results.read_text()
    )

    thresholds=experiment.get(
        "acceptance_rejection_thresholds"
    )

    if not thresholds:
        raise SystemExit(
            "FAIL: preregistered thresholds absent"
        )

    # The scorer never invents experiment-specific
    # interpretation. Canonical execution must provide
    # endpoint evaluation against the frozen thresholds.

    required={
        "endpoint_evaluations",
        "all_acceptance_thresholds_met",
        "any_rejection_threshold_triggered",
        "infrastructure_failure_before_evaluation",
    }

    missing=required-set(actual)

    if missing:
        raise SystemExit(
            "FAIL: result fields missing: "
            + ",".join(sorted(missing))
        )

    if actual[
        "infrastructure_failure_before_evaluation"
    ]:
        verdict="INCONCLUSIVE"

    elif actual[
        "any_rejection_threshold_triggered"
    ]:
        verdict="FAIL"

    elif actual[
        "all_acceptance_thresholds_met"
    ]:
        verdict="PASS"

    else:
        verdict="INCONCLUSIVE"

    scored={
        "experiment_id":
            experiment["experiment_id"],

        "frozen_thresholds":
            thresholds,

        "endpoint_evaluations":
            actual["endpoint_evaluations"],

        "verdict":
            verdict,

        "threshold_modified_after_results":
            False
    }

    output.write_text(
        json.dumps(scored,indent=2)+"\n"
    )

    print(json.dumps(scored,indent=2))


if __name__=="__main__":
    main()
