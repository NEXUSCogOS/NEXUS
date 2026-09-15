#!/usr/bin/env python3
"""Process B: Librarian independently claims MISSION L and executes real
bounded research against its real, governed academic corpus.

Subprocess 2 of the F6 four-process E2E test. Runs with NO knowledge of
Sentinel's mission or result (independence requirement, mission section 6)
-- this process never imports or touches anything Sentinel-related.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

FEDERATION_ROOT = str(Path(__file__).resolve().parents[4] / "nexus_federation")
LIBRARIAN_ROOT = str(Path(FEDERATION_ROOT).parent / "librarian")
DAT_AI_ROOT = str(Path(FEDERATION_ROOT).parent / "dat_ai")

for _p in (FEDERATION_ROOT, LIBRARIAN_ROOT, DAT_AI_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ingress.contract_registry import bootstrap_federation_registry
from _resource_accounting import ResourceMeter
from persistence.db import FederationStore
from runtime.academic_research_executor import run_bounded_synthesis
from contracts.generic import (
    CapabilityLifecycle,
    CapabilityStatus,
    Confidence,
    OperatingState,
    build_report,
)

RESEARCH_QUESTION = (
    "What authoritative policy, planning, or economic research supports, "
    "weakens, or contradicts the potential significance of a general "
    "construction plan for Cam Duong commune (Long Thanh district, Dong "
    "Nai province, Vietnam), given its geometric proximity "
    "(~1.2km boundary distance) to Long Thanh International Airport?"
)
QUERY_TERMS = (
    "airport infrastructure economic development land use Vietnam "
    "Long Thanh Dong Nai industrial logistics"
)
# 3, not the executor's own default of 2: at 2, generic terms like
# "economic"/"development" produce spurious matches against an
# all-technical-preprint corpus (verified during F6 construction: 9
# retrieved sources, heuristically "CONTRADICTORY" from incidental
# language, not a real position on this question). At 3, retrieval
# narrows to 4 sources and honestly reports INSUFFICIENT_EVIDENCE. Not
# tuned further to force a particular outcome.
MIN_MATCHED_TERMS = 3


def run():
    meter = ResourceMeter().start()
    bootstrap_federation_registry()

    store_path = os.environ.get("FEDERATION_STORE_PATH")
    mission_id = os.environ.get("MISSION_ID")
    delegation_id = os.environ.get("DELEGATION_ID")
    if not all([store_path, mission_id, delegation_id]):
        raise ValueError("Missing required environment variables")

    store = FederationStore(store_path)

    claim_id = str(uuid4())
    claimed = store.claim_delegation(
        delegation_id=delegation_id,
        claim_id=claim_id,
        claimed_by="librarian",
        claimed_at=datetime.now(timezone.utc).isoformat(),
    )
    if not claimed:
        result = {"pid": os.getpid(), "already_claimed": True, "report_id": None, "resource_usage": meter.stop()}
        print(json.dumps(result, indent=2))
        return 0

    synthesis = run_bounded_synthesis(
        research_question=RESEARCH_QUESTION,
        query_terms=QUERY_TERMS,
        data_dir=Path(LIBRARIAN_ROOT) / "data",
        min_matched_terms=MIN_MATCHED_TERMS,
    )

    findings_text = []
    evidence_refs = []
    limitations = list(synthesis.limitations)
    limitations.append(
        "CORPUS_SCOPE: Librarian's only governed corpus is a 22-source "
        "academic preprint collection (source_count_by_type: "
        "ACADEMIC_PREPRINT=22, per data/ACADEMIC_CORPUS_REGISTER.json) -- "
        "no separate government/policy-document corpus or interface is "
        "available to Librarian in this environment. This report cannot "
        "claim to have checked authoritative Vietnamese government "
        "planning/economic sources directly; DAT.AI's own ingestion "
        "(quyhoach.xaydung.gov.vn) is the only authoritative government "
        "source in this mission's evidence chain, and it originates from "
        "DAT.AI, not Librarian."
    )

    claim_class = "INSUFFICIENT_EVIDENCE"
    for f in synthesis.findings:
        status = f.support_status.value if hasattr(f.support_status, "value") else str(f.support_status)
        findings_text.append(
            f"{status}: {f.basis_for_status} (research question: {f.claim[:100]}...)"
        )
        evidence_refs.extend(f.evidence_refs)
        claim_class = status

    for g in synthesis.gaps:
        gtype = g.gap_type.value if hasattr(g, "gap_type") else str(g)
        findings_text.append(f"INSUFFICIENT_EVIDENCE: research gap classified as {gtype}")
        claim_class = "INSUFFICIENT_EVIDENCE"

    # One real, honestly-scoped SOURCE_FACT: a tangentially-related paper
    # exists in the corpus about land-use mapping methodology (found
    # during F6 construction, arxiv:1908.03438) -- real, but about
    # classification technique, not about economic/policy impact. Include
    # it only if it's actually among the retrieved evidence_refs (never
    # asserted independent of what was actually retrieved).
    if "arxiv:1908.03438" in evidence_refs:
        findings_text.append(
            "SOURCE_FACT: the corpus contains one paper on deep-learning-"
            "based land-use mapping methodology (arxiv:1908.03438) -- "
            "topically adjacent (land-use classification technique) but "
            "does NOT address economic or policy impact of infrastructure "
            "proximity, so it does not resolve this mission's actual "
            "research question."
        )

    report = build_report(
        institution="librarian",
        mission_id=mission_id,
        objective="Determine authoritative policy/economic/research context for a DAT.AI zoning finding",
        operating_state=OperatingState.TESTED,
        capability_statuses=[
            CapabilityStatus(
                name="cross_domain_research",
                lifecycle=CapabilityLifecycle.TESTED,
                confidence=Confidence(value=0.3, basis=f"real retrieval executed, {len(evidence_refs)} source(s) found, corpus is domain-mismatched for this question"),
                evidence_refs=evidence_refs or ["retrieval_executed_zero_sources"],
                detail=f"claim_class={claim_class}",
            )
        ],
        findings=findings_text,
        evidence_refs=evidence_refs or ["academic_corpus_query_executed"],
        limitations=limitations,
        provenance_refs=[delegation_id, claim_id],
    )

    report_id = str(uuid4())
    store.log_institutional_report(
        institution_id="librarian",
        mission_id=mission_id,
        report_id=report_id,
        payload=report.model_dump(),
    )
    store.commit()

    result = {
        "pid": os.getpid(),
        "already_claimed": False,
        "mission_id": mission_id,
        "delegation_id": delegation_id,
        "claim_id": claim_id,
        "report_id": report_id,
        "claim_class": claim_class,
        "sources_retrieved": len(evidence_refs),
        "evidence_refs": evidence_refs,
        "federation_store_path": store_path,
        "resource_usage": meter.stop(),
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
