from __future__ import annotations


def dossier_entry(
    experiment: dict,
    release_manifest: dict,
    publication_eligible: bool,
) -> dict:

    if publication_eligible is not True:

        return {
            "experiment_id":
                experiment["experiment_id"],
            "eligible":False,
            "reason":
                "VALIDATED_PUBLICATION_EVIDENCE_REQUIRED"
        }

    return {
        "experiment_id":
            experiment["experiment_id"],
        "eligible":True,
        "claim":
            release_manifest["claim"],
        "final_verdict":
            experiment["final_verdict"],
        "evidence_bundle_sha256":
            release_manifest[
                "bundle_manifest_sha256"
            ],
        "source_registry_id":
            release_manifest[
                "source_registry_id"
            ]
    }
