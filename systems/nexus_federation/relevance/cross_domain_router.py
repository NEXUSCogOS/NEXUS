"""Cross-domain relevance assessment and mission decomposition.

New module, NEXUS Federation F6. `relevance/router.py` (F1/F3) is a
single-signal-to-single-recipient mechanism (`ROUTING_TABLE["zoning_change"]
= "sentinel"`) -- correct for its own scope, but F6's hypothesis requires
NEXUS to recognize that ONE finding can carry implications in MULTIPLE
domains simultaneously and decompose it into independently-delegatable
missions. That is a genuinely different shape of decision (fan-out, not
lookup), so this is an additive new module, not a modification of the
existing router -- `router.py`'s own tests and its DAT.AI-specific
single-recipient contract are untouched.

Every relevance decision here is a named, explicit, inspectable boolean
check against the trigger's own declared fields -- never a learned score,
never routed "because the institution exists" (mission F6 section 4's
explicit prohibition).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import NAMESPACE_URL, uuid5

from budget.schema import DEFAULT_ANALYSIS_ONLY_BUDGET
from delegation.idempotency import compute_idempotency_key
from delegation.schema import DelegationProposal, RiskClass
from authority.model import AuthorityLevel

# Institutions this router knows how to evaluate. Extending this requires a
# deliberate new named check function below, not a generic fallback.
KNOWN_TARGET_INSTITUTIONS = ("librarian", "sentinel")


@dataclass(frozen=True)
class CrossDomainTrigger:
    """The F6 trigger object (mission section 3), as NEXUS holds it
    in-process. Field names match the mission's required schema; this
    dataclass is what F6_TRIGGER_EVIDENCE.json is built from and what
    `assess_cross_domain_relevance` consumes."""

    trigger_id: str
    source_institution: str
    source_report_id: str
    source_finding_id: str
    observation_timestamp: str
    received_timestamp: str
    evidence_refs: list[str]
    provenance_refs: list[str]
    claim_class: str  # e.g. "OBSERVED" | "DERIVED" -- from the source finding
    geography: str
    materiality: float
    materiality_basis: str
    uncertainty: list[str]
    limitations: list[str]
    freshness: str  # e.g. "CURRENT" | "STALE" relative to observation_timestamp
    candidate_implications: list[str]  # hypotheses for routing, NOT facts


@dataclass(frozen=True)
class InstitutionRelevance:
    """One institution's relevance determination -- always carries a
    reason, whether relevant or not, so a `False` is as auditable as a
    `True`."""

    institution: str
    relevant: bool
    reason: str
    matched_criteria: list[str] = field(default_factory=list)


def _assess_librarian(trigger: CrossDomainTrigger) -> InstitutionRelevance:
    """Librarian is relevant if the trigger's candidate implications
    include a policy/research/economic-context hypothesis AND the
    underlying claim traces to a real, citable government/authoritative
    source (not a bare assertion) -- Librarian's bounded-research
    commissioning is for authoritative source synthesis, not opinion."""

    policy_tags = {"policy", "economic", "research", "planning_precedent"}
    matched = [t for t in trigger.candidate_implications if t in policy_tags]

    has_authoritative_source = any(
        ref.startswith("source_url:") for ref in trigger.evidence_refs
    )

    if matched and has_authoritative_source:
        return InstitutionRelevance(
            institution="librarian",
            relevant=True,
            reason=(
                f"candidate_implications include policy/research-relevant "
                f"tag(s) {matched!r}, and the trigger cites a real, "
                f"traceable authoritative source ({[r for r in trigger.evidence_refs if r.startswith('source_url:')][0]}) "
                f"-- not a bare assertion. Librarian's commissioned "
                f"bounded-research capability can independently verify "
                f"policy/economic/research context for this geography."
            ),
            matched_criteria=matched,
        )
    return InstitutionRelevance(
        institution="librarian",
        relevant=False,
        reason=(
            f"no policy/research/economic candidate_implication tag found "
            f"(has={trigger.candidate_implications!r})"
            if not matched
            else "no traceable authoritative source_url in evidence_refs"
        ),
    )


def _assess_sentinel(trigger: CrossDomainTrigger) -> InstitutionRelevance:
    """Sentinel is relevant if the trigger's candidate implications
    include a financial/economic/sector hypothesis AND the geography is
    one Sentinel's covered market (Vietnamese equities, per
    SENTINEL_INSTITUTIONAL_CONTRACT.md) -- routing to Sentinel for a
    geography it has no data for would be routing "because it exists,"
    exactly what this mission prohibits."""

    financial_tags = {"economic", "sector", "company", "financial"}
    matched = [t for t in trigger.candidate_implications if t in financial_tags]

    geography_covered = "vietnam" in trigger.geography.lower() or "vn" in trigger.geography.lower().split()

    if matched and geography_covered:
        return InstitutionRelevance(
            institution="sentinel",
            relevant=True,
            reason=(
                f"candidate_implications include financial/sector-relevant "
                f"tag(s) {matched!r}, and geography ({trigger.geography!r}) "
                f"is within Sentinel's covered market (Vietnamese "
                f"equities). Sentinel's read-only analysis executor can "
                f"check its real universe for any company/sector with "
                f"declared exposure to this geography."
            ),
            matched_criteria=matched,
        )
    reasons = []
    if not matched:
        reasons.append(f"no financial/sector/company candidate_implication tag found (has={trigger.candidate_implications!r})")
    if not geography_covered:
        reasons.append(f"geography {trigger.geography!r} not within Sentinel's covered market")
    return InstitutionRelevance(institution="sentinel", relevant=False, reason="; ".join(reasons))


_ASSESSORS = {
    "librarian": _assess_librarian,
    "sentinel": _assess_sentinel,
}


def assess_cross_domain_relevance(
    trigger: CrossDomainTrigger,
) -> list[InstitutionRelevance]:
    """Deterministic, inspectable relevance assessment against every known
    target institution. Returns one InstitutionRelevance per institution
    in KNOWN_TARGET_INSTITUTIONS, relevant or not -- the negative
    determinations are as important to persist as the positive ones
    (mission section 4: "Record WHY each institution is relevant")."""

    if trigger.materiality < 0.0 or trigger.materiality > 1.0:
        raise ValueError("materiality must be within [0.0, 1.0]")
    if not trigger.materiality_basis:
        raise ValueError("materiality requires a stated basis")
    if not trigger.evidence_refs:
        raise ValueError("a trigger with no evidence_refs cannot be assessed for relevance")

    return [_ASSESSORS[inst](trigger) for inst in KNOWN_TARGET_INSTITUTIONS]


@dataclass(frozen=True)
class AttentionAssessment:
    """Mission section 24: why a trigger warranted executive attention,
    scored by fixed, transparent rules -- never an opaque/learned
    "importance" number. Each factor is boolean or a small ordinal, and
    the total is their literal sum: fully reproducible by hand from the
    trigger's own fields."""

    evidence_quality_score: int          # 0-2: 0=no authoritative source, 1=single source, 2=government-authoritative source
    materiality_score: int               # 0-2: trigger.materiality bucketed (<0.3 / 0.3-0.6 / >0.6)
    geographic_scope_score: int          # 0-1: 1 if geography is a named, specific place (not a whole country/region)
    cross_domain_relevance_score: int    # 0-2: count of institutions found relevant (0, 1, or 2)
    novelty_score: int                   # 0-1: always 1 in this harness (no prior-trigger deduplication corpus exists to check against; NOT fabricated as 0)
    time_sensitivity_score: int          # 0-1: 0 if freshness is STALE_BUT_USABLE, 1 if CURRENT
    institutional_coverage_score: int    # 0-1: 1 if >=2 institutions in KNOWN_TARGET_INSTITUTIONS were evaluated (always 1 here)
    uncertainty_penalty: int             # 0 to -2: -1 per limitation/uncertainty item beyond the first 2, capped at -2
    total_score: int
    requires_attention: bool             # total_score >= ATTENTION_THRESHOLD
    basis: str


ATTENTION_THRESHOLD = 4


def assess_attention(
    trigger: CrossDomainTrigger, relevances: list[InstitutionRelevance]
) -> AttentionAssessment:
    has_gov_source = any(
        ref.startswith("source_url:") and (".gov" in ref or "quyhoach.xaydung" in ref)
        for ref in trigger.evidence_refs
    )
    has_any_source = any(ref.startswith("source_url:") for ref in trigger.evidence_refs)
    evidence_quality = 2 if has_gov_source else (1 if has_any_source else 0)

    materiality = 2 if trigger.materiality > 0.6 else (1 if trigger.materiality >= 0.3 else 0)

    # A specific administrative geography (commune/district named), not
    # merely "Vietnam" or "Southeast Asia".
    geographic_scope = 1 if trigger.geography.count(",") >= 1 else 0

    relevant_count = sum(1 for r in relevances if r.relevant)
    cross_domain = min(2, relevant_count)

    novelty = 1  # see field docstring -- not fabricated as an unearned 0

    time_sensitivity = 1 if trigger.freshness == "CURRENT" else 0

    institutional_coverage = 1 if len(relevances) >= 2 else 0

    penalty_items = len(trigger.uncertainty) + len(trigger.limitations)
    uncertainty_penalty = -min(2, max(0, penalty_items - 2))

    total = (
        evidence_quality + materiality + geographic_scope + cross_domain
        + novelty + time_sensitivity + institutional_coverage + uncertainty_penalty
    )

    return AttentionAssessment(
        evidence_quality_score=evidence_quality,
        materiality_score=materiality,
        geographic_scope_score=geographic_scope,
        cross_domain_relevance_score=cross_domain,
        novelty_score=novelty,
        time_sensitivity_score=time_sensitivity,
        institutional_coverage_score=institutional_coverage,
        uncertainty_penalty=uncertainty_penalty,
        total_score=total,
        requires_attention=total >= ATTENTION_THRESHOLD,
        basis=(
            f"evidence_quality={evidence_quality}(gov_source={has_gov_source}) + "
            f"materiality={materiality}({trigger.materiality}) + "
            f"geographic_scope={geographic_scope} + "
            f"cross_domain_relevance={cross_domain}({relevant_count} institutions) + "
            f"novelty={novelty} + time_sensitivity={time_sensitivity}"
            f"(freshness={trigger.freshness}) + "
            f"institutional_coverage={institutional_coverage} + "
            f"uncertainty_penalty={uncertainty_penalty} = {total} "
            f"(threshold={ATTENTION_THRESHOLD})"
        ),
    )


def build_mission_l_librarian(trigger: CrossDomainTrigger, relevance: InstitutionRelevance) -> DelegationProposal:
    """MISSION L (mission section 5's example structure)."""
    if not relevance.relevant:
        raise ValueError("cannot build a Librarian delegation from a negative relevance determination")

    objective = (
        f"Determine the authoritative policy, planning, economic and "
        f"research context relevant to this DAT.AI finding "
        f"(project_id/administrative area: {trigger.source_finding_id}, "
        f"geography: {trigger.geography}), including evidence that "
        f"supports, weakens, or contradicts its potential significance. "
        f"Distinguish SOURCE_FACT, DERIVED_SYNTHESIS, INFERENCE, "
        f"HYPOTHESIS, CONTRADICTION, and INSUFFICIENT_EVIDENCE explicitly."
    )
    idempotency_key = compute_idempotency_key(
        institution=trigger.source_institution,
        cycle_id=trigger.trigger_id,
        capability_name="cross_domain_research",
        category="zoning_change_librarian_research",
    )
    # Deterministic, not the schema's random default -- see the module
    # docstring on record_delegation_proposal's OWN idempotency notion
    # (mission_id:proposal_id, persistence/db.py) in F6_TRIGGER_EVIDENCE
    # notes: proposal_id must also be trigger-derived, or a replay with
    # an identical mission_id would still persist as a second row under
    # a different composite key.
    proposal_id = str(uuid5(NAMESPACE_URL, f"f6-delegation:{trigger.trigger_id}:librarian"))

    return DelegationProposal(
        mission_id=f"{trigger.trigger_id}-mission-l",
        proposal_id=proposal_id,
        recipient="librarian",
        objective=objective,
        reason=relevance.reason,
        evidence_refs=list(trigger.evidence_refs),
        priority=2,
        authority=AuthorityLevel.RESEARCH,
        constraints=[
            "no external publication",
            "no modification of another institution",
            "no architectural change",
            "research/analysis only",
        ],
        resource_budget=DEFAULT_ANALYSIS_ONLY_BUDGET,
        success_criteria=["Librarian returns an InstitutionalReport with claim-class-tagged findings"],
        risk_class=RiskClass.MEDIUM if trigger.materiality >= 0.5 else RiskClass.LOW,
        parent_mission=trigger.trigger_id,
        idempotency_key=idempotency_key,
    )


def build_mission_s_sentinel(trigger: CrossDomainTrigger, relevance: InstitutionRelevance) -> DelegationProposal:
    """MISSION S (mission section 5's example structure)."""
    if not relevance.relevant:
        raise ValueError("cannot build a Sentinel delegation from a negative relevance determination")

    objective = (
        f"Using verified currently available financial data, assess "
        f"whether sectors or listed companies could plausibly be exposed "
        f"to the economic implications of this DAT.AI finding "
        f"(project_id/administrative area: {trigger.source_finding_id}, "
        f"geography: {trigger.geography}). Distinguish "
        f"OBSERVED_MARKET_FACT, DERIVED_METRIC, MODEL_ESTIMATE, SIGNAL, "
        f"RECOMMENDATION, and UNKNOWN. Do not execute trades."
    )
    idempotency_key = compute_idempotency_key(
        institution=trigger.source_institution,
        cycle_id=trigger.trigger_id,
        capability_name="cross_domain_financial_analysis",
        category="zoning_change_sentinel_analysis",
    )
    proposal_id = str(uuid5(NAMESPACE_URL, f"f6-delegation:{trigger.trigger_id}:sentinel"))

    return DelegationProposal(
        mission_id=f"{trigger.trigger_id}-mission-s",
        proposal_id=proposal_id,
        recipient="sentinel",
        objective=objective,
        reason=relevance.reason,
        evidence_refs=list(trigger.evidence_refs),
        priority=2,
        authority=AuthorityLevel.ANALYSE,
        constraints=[
            "no external publication",
            "no modification of another institution",
            "no architectural change",
            "no financial execution: no order placement, no order "
            "cancellation, no execution_mode change, no execution_allowed "
            "change, no broker invocation",
        ],
        resource_budget=DEFAULT_ANALYSIS_ONLY_BUDGET,
        success_criteria=["Sentinel returns an InstitutionalReport with epistemically-tagged findings"],
        risk_class=RiskClass.MEDIUM if trigger.materiality >= 0.5 else RiskClass.LOW,
        parent_mission=trigger.trigger_id,
        idempotency_key=idempotency_key,
    )
