"""Minimal executive relevance assessment.

New module, NEXUS Federation F1. Deterministic and testable: given a
structured relevance signal (not free-text findings parsed by keyword
matching, which would not be a defensible mechanism), decide whether a
delegation proposal should be generated, and to which institution.

Honest limitation, stated rather than hidden: DAT.AI's current contract
has no structured field for "a material zoning/planning change occurred at
location X" -- its findings today are capability-status strings (e.g.
"zoning_api: INTEGRATED -- ..."). This module is built to correctly *not*
trigger any delegation from those routine status findings (proven by test),
and to correctly trigger one when given a signal shaped like what a future
real change-detection capability would emit (also proven by test, using an
explicitly-labeled synthetic fixture -- see
tests/unit/test_relevance_router.py). No delegation in this mission is ever
generated from real, currently-flowing DAT.AI data, because DAT.AI does not
yet emit change-detection findings; the mechanism is proven correct and
ready for when it does.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from budget.schema import DEFAULT_ANALYSIS_ONLY_BUDGET
from delegation.idempotency import compute_idempotency_key
from delegation.schema import DelegationProposal, RiskClass
from state.capability import lifecycle_rank

MATERIALITY_THRESHOLD = 0.5
MIN_LIFECYCLE_RANK = lifecycle_rank("TESTED")

# Explicit, deterministic routing table -- not inferred, not learned.
ROUTING_TABLE: dict[str, str] = {
    "zoning_change": "sentinel",  # land-use change has financial materiality
    # NEXUS Federation F3: routes a bounded research request to Librarian.
    # See runtime/research_executor.py (Librarian side) and
    # NEXUS_LIBRARIAN_DELEGATION_E2E_EVIDENCE.md for the real, executed
    # end-to-end proof.
    "research_request": "librarian",
}


@dataclass(frozen=True)
class RelevanceSignal:
    """A structured signal for relevance assessment. Materiality MUST carry
    a stated basis (mirrors the Confidence discipline in DAT.AI's own
    contract) -- an unstated numeric materiality is not accepted."""

    institution: str
    capability_name: str
    category: str
    materiality: float
    materiality_basis: str
    evidence_refs: list[str]
    parent_mission_id: str
    geography: Optional[str] = None

    def __post_init__(self):
        if not (0.0 <= self.materiality <= 1.0):
            raise ValueError("materiality must be within [0.0, 1.0]")
        if not self.materiality_basis:
            raise ValueError(
                "materiality requires a stated basis -- no fabricated "
                "numeric materiality is accepted here, mirroring DAT.AI's "
                "own Confidence discipline"
            )


def assess_relevance(
    signal: RelevanceSignal, *, capability_lifecycle: str
) -> Optional[DelegationProposal]:
    """Returns a DelegationProposal, or None if no delegation is warranted.

    Every gate below is a named, explicit, deterministic check -- there is
    no scoring function, no learned weight, nothing that could produce a
    different answer for the same input on a different run.
    """
    if signal.category not in ROUTING_TABLE:
        return None
    if signal.materiality < MATERIALITY_THRESHOLD:
        return None
    if not signal.evidence_refs:
        return None
    rank = lifecycle_rank(capability_lifecycle)
    if rank is None or rank < MIN_LIFECYCLE_RANK:
        # Do not delegate off an untested/unintegrated capability's output.
        return None

    recipient = ROUTING_TABLE[signal.category]
    risk = RiskClass.HIGH if signal.materiality >= 0.8 else RiskClass.MEDIUM

    idempotency_key = compute_idempotency_key(
        institution=signal.institution,
        cycle_id=signal.parent_mission_id,
        capability_name=signal.capability_name,
        category=signal.category,
    )

    if signal.category == "research_request":
        # NEXUS Federation F3: the research QUESTION itself is carried in
        # materiality_basis (already required, free-text, and exactly the
        # right shape: "why this matters" IS the research objective for a
        # request category, rather than inventing a new schema field).
        objective = signal.materiality_basis
    else:
        objective = f"Assess financial/institutional implications of a {signal.category} reported by {signal.institution}"

    return DelegationProposal(
        mission_id=f"{signal.parent_mission_id}-delegation",
        recipient=recipient,
        objective=objective,
        reason=(
            f"{signal.institution}.{signal.capability_name} reported a "
            f"{signal.category} with materiality={signal.materiality} "
            f"(basis: {signal.materiality_basis})"
            + (f" at {signal.geography}" if signal.geography else "")
        ),
        evidence_refs=list(signal.evidence_refs),
        priority=1 if risk == RiskClass.HIGH else 3,
        resource_budget=DEFAULT_ANALYSIS_ONLY_BUDGET,
        constraints=[
            "analysis only -- no financial execution authorized",
            f"triggering capability lifecycle was {capability_lifecycle!r} at delegation time",
        ],
        success_criteria=[
            f"{recipient} returns an InstitutionalReport addressing the objective"
        ],
        risk_class=risk,
        parent_mission=signal.parent_mission_id,
        idempotency_key=idempotency_key,
    )
