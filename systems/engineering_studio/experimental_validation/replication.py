from __future__ import annotations

from pathlib import Path

from .bundle_sealer import verify_bundle


VALID_PREDECESSOR_VERDICTS = {
    "SUPPORTED",
    "REJECTED",
    "QUALIFIED",
    "INCONCLUSIVE",
}


def validate_predecessor(
    predecessor: dict,
    bundle_manifest: Path | None,
    bundle_dir: Path | None,
    independent_replicator_pass: bool,
    clean_environment_pass: bool,
) -> dict:

    reasons=[]

    if (
        predecessor.get("result_status")
        != "COMPLETED"
    ):
        reasons.append(
            "PREDECESSOR_NOT_COMPLETED"
        )

    verdict=predecessor.get(
        "final_verdict"
    )

    if verdict not in VALID_PREDECESSOR_VERDICTS:

        reasons.append(
            "PREDECESSOR_VERDICT_NOT_VALID"
        )

    if not bundle_manifest or not bundle_dir:

        reasons.append(
            "SEALED_BUNDLE_MISSING"
        )

    else:

        try:

            result=verify_bundle(
                bundle_manifest,
                bundle_dir
            )

            if not result["valid"]:
                reasons.append(
                    "SEALED_BUNDLE_INVALID"
                )

        except Exception:

            reasons.append(
                "SEALED_BUNDLE_INVALID"
            )

    if independent_replicator_pass is not True:

        reasons.append(
            "INDEPENDENT_REPLICATOR_REQUIRED"
        )

    if clean_environment_pass is not True:

        reasons.append(
            "CLEAN_REPLICATION_ENVIRONMENT_REQUIRED"
        )

    return {
        "eligible":
            len(reasons)==0,
        "reasons":
            reasons
    }
