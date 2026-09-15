from __future__ import annotations

from typing import Any


ALLOWED_VERDICTS = {
    "SUPPORTED",
    "REJECTED",
    "QUALIFIED",
    "INCONCLUSIVE",
    "INVALID",
}


def score_threshold(
    observed: float,
    operator: str,
    threshold: float,
) -> bool:

    operations = {
        ">=": lambda a,b: a >= b,
        "<=": lambda a,b: a <= b,
        ">": lambda a,b: a > b,
        "<": lambda a,b: a < b,
        "==": lambda a,b: a == b,
    }

    if operator not in operations:
        raise ValueError(
            f"Unsupported operator: {operator}"
        )

    return operations[operator](
        observed,
        threshold
    )


def score_endpoints(
    preregistered_endpoints: list[dict],
    observations: dict[str, Any],
) -> dict:

    results=[]

    for endpoint in preregistered_endpoints:

        name=endpoint["name"]

        if name not in observations:

            results.append({
                "name":name,
                "status":"MISSING",
                "passed":False
            })

            continue

        observed=observations[name]

        passed=score_threshold(
            observed,
            endpoint["operator"],
            endpoint["threshold"]
        )

        results.append({
            "name":name,
            "observed":observed,
            "operator":endpoint["operator"],
            "threshold":endpoint["threshold"],
            "passed":passed,
            "status":
                "PASS" if passed else "FAIL"
        })

    return {
        "endpoint_count":len(results),
        "passed_count":
            sum(x["passed"] for x in results),
        "failed_count":
            sum(not x["passed"] for x in results),
        "endpoints":results
    }


def determine_verdict(
    scoring: dict,
    invalidated: bool = False,
) -> str:

    if invalidated:
        return "INVALID"

    if scoring["endpoint_count"] == 0:
        return "INCONCLUSIVE"

    missing=any(
        x["status"]=="MISSING"
        for x in scoring["endpoints"]
    )

    if missing:
        return "INCONCLUSIVE"

    passed=scoring["passed_count"]
    total=scoring["endpoint_count"]

    if passed == total:
        return "SUPPORTED"

    if passed == 0:
        return "REJECTED"

    return "QUALIFIED"
