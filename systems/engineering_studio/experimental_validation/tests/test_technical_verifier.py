from pathlib import Path
import tempfile

from experimental_validation.technical_verifier import (
    TECHNICAL_GATES,
    verify,
    verify_all,
)


def main():
    assert len(TECHNICAL_GATES) == 10

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        results = verify_all(str(root))

        assert len(results) == 10

        ids = {
            x["gate_id"]
            for x in results
        }

        assert ids == set(
            TECHNICAL_GATES
        )

        for item in results:
            assert (
                item[
                    "formal_gate_pass_created"
                ]
                is False
            )

            assert item["status"] in {
                "OBSERVED",
                "HUMAN_REVIEW_REQUIRED",
                "NOT_TESTABLE_DURING_COMMISSIONING",
                "NOT_TESTABLE",
                "FAIL",
            }

        # Disk check is an observation,
        # never an automatic PASS.
        disk = verify(
            "NEXUS-EXP-005-04",
            str(root)
        )

        assert disk["status"] == "OBSERVED"
        assert disk["formal_gate_pass_created"] is False
        assert "free_bytes" in disk

        # Unknown gates cannot pass.
        unknown = verify(
            "fake-gate-999",
            str(root)
        )

        assert (
            unknown["status"]
            == "NOT_TECHNICAL_GATE"
        )

    print(
        "PASS: ten technical verifier "
        "fail-closed tests"
    )


if __name__ == "__main__":
    main()
