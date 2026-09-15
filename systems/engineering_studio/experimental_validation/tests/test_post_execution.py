import json
import tempfile
from pathlib import Path

from experimental_validation.result_validator import (
    score_endpoints,
    determine_verdict,
)

from experimental_validation.bundle_sealer import (
    seal_bundle,
    verify_bundle,
)

from experimental_validation.replication import (
    validate_predecessor,
)


def main():

    # ---------------------------------------------
    # Scoring
    # ---------------------------------------------

    endpoints=[
        {
            "name":"accuracy",
            "operator":">=",
            "threshold":0.90
        },
        {
            "name":"error_rate",
            "operator":"<=",
            "threshold":0.05
        }
    ]

    observations={
        "accuracy":0.95,
        "error_rate":0.02
    }

    scoring=score_endpoints(
        endpoints,
        observations
    )

    assert scoring["passed_count"]==2
    assert (
        determine_verdict(scoring)
        ==
        "SUPPORTED"
    )


    # Missing endpoint cannot produce support.
    scoring=score_endpoints(
        endpoints,
        {"accuracy":0.95}
    )

    assert (
        determine_verdict(scoring)
        ==
        "INCONCLUSIVE"
    )


    # ---------------------------------------------
    # Bundle
    # ---------------------------------------------

    with tempfile.TemporaryDirectory() as td:

        root=Path(td)
        bundle=root/"bundle"
        bundle.mkdir()

        evidence=bundle/"result.json"

        evidence.write_text(
            json.dumps({
                "result":"synthetic"
            })
        )

        manifest=root/"manifest.json"

        seal_bundle(
            "TEST-EXP",
            bundle,
            manifest
        )

        verified=verify_bundle(
            manifest,
            bundle
        )

        assert verified["valid"] is True


        # Tamper with evidence.
        evidence.write_text(
            '{"result":"tampered"}'
        )

        verified=verify_bundle(
            manifest,
            bundle
        )

        assert verified["valid"] is False


    # ---------------------------------------------
    # EXP-006 must reject fake predecessor.
    # ---------------------------------------------

    fake={
        "experiment_id":"NEXUS-EXP-001",
        "result_status":"BLOCKED",
        "final_verdict":"PENDING"
    }

    result=validate_predecessor(
        fake,
        None,
        None,
        False,
        False
    )

    assert result["eligible"] is False

    assert (
        "PREDECESSOR_NOT_COMPLETED"
        in result["reasons"]
    )

    assert (
        "INDEPENDENT_REPLICATOR_REQUIRED"
        in result["reasons"]
    )

    print(
        "PASS: scoring/sealing/"
        "replication adversarial tests"
    )


if __name__=="__main__":
    main()
