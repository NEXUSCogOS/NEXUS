from __future__ import annotations

import json
import re
from pathlib import Path


ALLOWED_VERDICTS = {
    "SUPPORTED",
    "REJECTED",
    "QUALIFIED",
    "INCONCLUSIVE",
}


def publication_eligibility(
    experiment: dict,
    sealed_bundle_valid: bool,
    replication_state: str | None,
) -> dict:

    reasons=[]

    if experiment.get("result_status") != "COMPLETED":
        reasons.append("EXPERIMENT_NOT_COMPLETED")

    verdict=experiment.get("final_verdict")

    if verdict not in ALLOWED_VERDICTS:
        reasons.append("FINAL_VERDICT_NOT_PUBLICATION_ELIGIBLE")

    if sealed_bundle_valid is not True:
        reasons.append("SEALED_BUNDLE_NOT_VALID")

    # Replication is recorded separately. Lack of replication does not
    # magically invalidate an original experiment, but must be disclosed.
    replication_disclosure=(
        replication_state
        if replication_state
        else "NOT_REPLICATED"
    )

    return {
        "eligible_for_staging":not reasons,
        "reasons":reasons,
        "replication_disclosure":replication_disclosure,
        "automatic_publication_authorized":False,
        "github_push_authorized":False,
    }


def calibrated_claim(experiment: dict) -> str:

    eid=experiment["experiment_id"]
    verdict=experiment.get("final_verdict")

    if verdict=="SUPPORTED":
        return (
            f"{eid}: preregistered acceptance criteria "
            "were satisfied in the reported experiment."
        )

    if verdict=="REJECTED":
        return (
            f"{eid}: preregistered acceptance criteria "
            "were not satisfied in the reported experiment."
        )

    if verdict=="QUALIFIED":
        return (
            f"{eid}: results were mixed relative to "
            "the preregistered acceptance criteria."
        )

    if verdict=="INCONCLUSIVE":
        return (
            f"{eid}: the reported experiment did not "
            "support a conclusive determination."
        )

    raise ValueError(
        "No public claim may be generated for a "
        "non-final or invalid verdict."
    )


PATTERNS={
    "credential_assignment":re.compile(
        r"(?i)\b(?:api[_-]?key|secret|password|passwd|"
        r"github_token|gh_token|access_token)\b\s*[:=]\s*\S+"
    ),

    "github_pat":re.compile(
        r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"
    ),

    "email_pii":re.compile(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    ),

    "absolute_user_path":re.compile(
        r"/Users/[^/\s]+(?:/[^\s]*)?"
    ),

    "absolute_volume_path":re.compile(
        r"/Volumes/[^/\s]+(?:/[^\s]*)?"
    ),

    "private_ipv4":re.compile(
        r"\b(?:"
        r"10(?:\.\d{1,3}){3}|"
        r"192\.168(?:\.\d{1,3}){2}|"
        r"172\.(?:1[6-9]|2\d|3[01])"
        r"(?:\.\d{1,3}){2}"
        r")\b"
    ),

    "strong_claim":re.compile(
        r"(?i)\b(?:"
        r"guaranteed|"
        r"proven superior|"
        r"best in the world|"
        r"universally superior|"
        r"definitively state[- ]of[- ]the[- ]art"
        r")\b"
    ),
}


def scan_staging(root: Path) -> dict:

    root=Path(root)

    findings={
        key:[]
        for key in PATTERNS
    }

    for path in root.rglob("*"):

        if not path.is_file():
            continue

        try:
            if path.stat().st_size > 2_000_000:
                continue

            text=path.read_text(errors="ignore")

        except Exception:
            continue

        for name,pattern in PATTERNS.items():

            for match in pattern.finditer(text):

                findings[name].append({
                    "path":str(path),
                    "match":match.group(0)[:200]
                })

    total=sum(
        len(v)
        for v in findings.values()
    )

    return {
        "clean":total==0,
        "finding_count":total,
        "findings":findings
    }


def provenance_check(release_manifest: dict) -> dict:

    reasons=[]

    required=(
        "experiment_id",
        "final_verdict",
        "bundle_manifest_sha256",
        "source_registry_id",
        "claim",
    )

    for field in required:

        value=release_manifest.get(field)

        if value in (None,"",[],{}):
            reasons.append(
                f"MISSING_PROVENANCE_FIELD:{field}"
            )

    if (
        release_manifest.get("source_registry_id")
        != "NEXUS-EVR-001"
    ):
        reasons.append(
            "NONCANONICAL_SOURCE_REGISTRY"
        )

    return {
        "valid":not reasons,
        "reasons":reasons
    }
