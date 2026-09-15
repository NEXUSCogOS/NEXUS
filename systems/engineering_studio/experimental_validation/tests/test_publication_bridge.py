import tempfile
from pathlib import Path

from experimental_validation.publication_bridge import (
    publication_eligibility,
    calibrated_claim,
    scan_staging,
    provenance_check,
)

from experimental_validation.dossier import (
    dossier_entry,
)


def main():

    blocked={
        "experiment_id":"TEST-EXP",
        "result_status":"BLOCKED",
        "final_verdict":"PENDING",
    }

    result=publication_eligibility(
        blocked,
        False,
        None
    )

    assert result["eligible_for_staging"] is False
    assert result["github_push_authorized"] is False


    completed={
        "experiment_id":"TEST-EXP",
        "result_status":"COMPLETED",
        "final_verdict":"SUPPORTED",
    }

    result=publication_eligibility(
        completed,
        True,
        "REPLICATION_PENDING"
    )

    assert result["eligible_for_staging"] is True
    assert result["github_push_authorized"] is False

    claim=calibrated_claim(completed)

    assert "preregistered" in claim.lower()


    manifest={
        "experiment_id":"TEST-EXP",
        "final_verdict":"SUPPORTED",
        "bundle_manifest_sha256":"a"*64,
        "source_registry_id":"NEXUS-EVR-001",
        "claim":claim,
    }

    assert provenance_check(manifest)["valid"]


    dossier=dossier_entry(
        completed,
        manifest,
        True
    )

    assert dossier["eligible"] is True


    # --------------------------------------------
    # Scanner must catch dangerous staging.
    # --------------------------------------------

    with tempfile.TemporaryDirectory() as td:

        root=Path(td)

        bad=root/"bad.txt"

        bad.write_text(
            "github_token=ghp_"
            + "A"*30
            + "\n"
            + "email=test@example.com\n"
            + "path=/Users/example/private/file\n"
            + "ip=192.168.1.20\n"
            + "this is guaranteed\n"
        )

        scan=scan_staging(root)

        assert scan["clean"] is False
        assert scan["finding_count"] >= 4


    # Pending experiment cannot enter dossier.
    dossier=dossier_entry(
        blocked,
        manifest,
        False
    )

    assert dossier["eligible"] is False


    print(
        "PASS: publication/dossier "
        "fail-closed tests"
    )


if __name__=="__main__":
    main()
