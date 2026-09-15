"""Event-driven relevance assessment and delegation for News
Intelligence events. NEXUS Federation F7, mission section 24.

Additive alongside relevance/router.py (F1/F3, single-recipient
lookup) and relevance/cross_domain_router.py (F6, DAT.AI-finding-driven,
2 recipients) -- this module is driven by a NEWS Event object and
considers THREE possible recipients (DAT.AI, Librarian, Sentinel), per
the mission's explicit list. Neither prior router is modified.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import NAMESPACE_URL, uuid5

from budget.schema import DEFAULT_ANALYSIS_ONLY_BUDGET
from delegation.schema import DelegationProposal, RiskClass
from authority.model import AuthorityLevel

KNOWN_TARGET_INSTITUTIONS = ("dat_ai", "librarian", "sentinel")

# DAT.AI has no real "receive a delegation and independently execute"
# capability in this federation as of F7 -- it has only ever been a
# report SOURCE (F6), never a RECIPIENT. This is an honest, disclosed
# capability gap, not silently worked around: if DAT.AI is assessed
# relevant, this router says so, but does not fabricate a DAT.AI
# execution.
EXECUTABLE_RECIPIENTS = ("librarian", "sentinel")

# Event types plausibly relevant to DAT.AI's geospatial/zoning domain.
_DAT_AI_RELEVANT_EVENT_TYPES = {"INFRASTRUCTURE", "PLANNING"}
_LIBRARIAN_RELEVANT_EVENT_TYPES = {
    "REGULATORY", "POLICY", "TECHNOLOGY", "MACROECONOMIC", "GEOPOLITICAL",
    "ENVIRONMENTAL", "EDUCATION", "LEGAL",
}
_SENTINEL_RELEVANT_EVENT_TYPES = {
    "EARNINGS", "CAPITAL_MARKETS", "M_AND_A", "CORPORATE", "SUPPLY_CHAIN",
    "COMMODITY",
}

MIN_MATERIALITY_FOR_ROUTING = 5


@dataclass(frozen=True)
class EventRelevance:
    institution: str
    relevant: bool
    reason: str
    executable: bool


def assess_event_relevance(
    *, event_type: str, materiality_score: int, locations: list[str],
    resolved_entities: list[str],
) -> list[EventRelevance]:
    """Deterministic, named-reason assessment against every known target
    institution -- never routed merely because the institution exists."""

    results = []

    if materiality_score < MIN_MATERIALITY_FOR_ROUTING:
        reason = f"materiality_score={materiality_score} below routing threshold ({MIN_MATERIALITY_FOR_ROUTING})"
        return [
            EventRelevance(inst, False, reason, inst in EXECUTABLE_RECIPIENTS)
            for inst in KNOWN_TARGET_INSTITUTIONS
        ]

    # DAT.AI
    dat_ai_relevant = event_type in _DAT_AI_RELEVANT_EVENT_TYPES and bool(locations)
    dat_ai_reason = (
        f"event_type={event_type!r} is geospatial/zoning-relevant and "
        f"{len(locations)} location(s) resolved: {locations}"
        if dat_ai_relevant else
        f"event_type={event_type!r} not in DAT.AI-relevant set "
        f"{sorted(_DAT_AI_RELEVANT_EVENT_TYPES)} or no locations resolved"
    )
    results.append(EventRelevance("dat_ai", dat_ai_relevant, dat_ai_reason, executable=False))

    # Librarian
    lib_relevant = event_type in _LIBRARIAN_RELEVANT_EVENT_TYPES
    lib_reason = (
        f"event_type={event_type!r} is policy/research-relevant"
        if lib_relevant else
        f"event_type={event_type!r} not in Librarian-relevant set {sorted(_LIBRARIAN_RELEVANT_EVENT_TYPES)}"
    )
    results.append(EventRelevance("librarian", lib_relevant, lib_reason, executable=True))

    # Sentinel
    sen_relevant = event_type in _SENTINEL_RELEVANT_EVENT_TYPES
    sen_reason = (
        f"event_type={event_type!r} is financial/corporate-relevant"
        if sen_relevant else
        f"event_type={event_type!r} not in Sentinel-relevant set {sorted(_SENTINEL_RELEVANT_EVENT_TYPES)}"
    )
    results.append(EventRelevance("sentinel", sen_relevant, sen_reason, executable=True))

    return results


def build_mission_for_institution(
    *, event_id: str, event_type: str, headline: str, materiality_score: int,
    evidence_refs: list[str], relevance: EventRelevance,
) -> DelegationProposal:
    if not relevance.relevant:
        raise ValueError(f"cannot build a delegation from a negative relevance determination ({relevance.institution})")

    objectives = {
        "librarian": (
            f"Determine the authoritative policy/research/economic "
            f"context relevant to the news event {headline!r} "
            f"(event_type={event_type}). Distinguish SOURCE_FACT, "
            f"DERIVED_SYNTHESIS, INFERENCE, HYPOTHESIS, CONTRADICTION, "
            f"and INSUFFICIENT_EVIDENCE explicitly."
        ),
        "sentinel": (
            f"Using verified currently available financial data, assess "
            f"whether any Sentinel-covered sector or listed company is "
            f"plausibly exposed to the news event {headline!r} "
            f"(event_type={event_type}). Distinguish "
            f"OBSERVED_MARKET_FACT, DERIVED_METRIC, MODEL_ESTIMATE, "
            f"SIGNAL, RECOMMENDATION, and UNKNOWN. Do not execute trades."
        ),
    }
    authorities = {"librarian": AuthorityLevel.RESEARCH, "sentinel": AuthorityLevel.ANALYSE}

    trigger_id = str(uuid5(NAMESPACE_URL, f"f7-trigger:{event_id}"))
    proposal_id = str(uuid5(NAMESPACE_URL, f"f7-delegation:{event_id}:{relevance.institution}"))

    return DelegationProposal(
        mission_id=f"{trigger_id}-mission-{relevance.institution}",
        proposal_id=proposal_id,
        recipient=relevance.institution,
        objective=objectives[relevance.institution],
        reason=relevance.reason,
        evidence_refs=list(evidence_refs),
        priority=1 if materiality_score >= 8 else 2,
        authority=authorities[relevance.institution],
        constraints=[
            "no external publication",
            "no modification of another institution",
            "no architectural change",
            "no financial execution" if relevance.institution == "sentinel" else "research/analysis only",
        ],
        resource_budget=DEFAULT_ANALYSIS_ONLY_BUDGET,
        success_criteria=[f"{relevance.institution} returns an InstitutionalReport addressing the objective"],
        risk_class=RiskClass.MEDIUM if materiality_score >= 6 else RiskClass.LOW,
        parent_mission=trigger_id,
        idempotency_key=str(uuid5(NAMESPACE_URL, f"f7-idempotency:{event_id}:{relevance.institution}")),
    )
