"""UNIT tests: deterministic relevance/delegation router."""

from __future__ import annotations

import pytest

from relevance.router import MATERIALITY_THRESHOLD, RelevanceSignal, assess_relevance


def _signal(**overrides) -> RelevanceSignal:
    base = dict(
        institution="dat_ai",
        capability_name="zoning_api",
        category="zoning_change",
        materiality=0.9,
        materiality_basis="test fixture: synthetic change signal",
        evidence_refs=["docs/DATAI_CHARTER.md"],
        parent_mission_id="test-mission",
        geography="Dong Nai",
    )
    base.update(overrides)
    return RelevanceSignal(**base)


def test_material_change_with_tested_capability_produces_delegation():
    proposal = assess_relevance(_signal(), capability_lifecycle="INTEGRATED")
    assert proposal is not None
    assert proposal.recipient == "sentinel"
    assert proposal.parent_mission == "test-mission"
    assert proposal.evidence_refs


def test_low_materiality_produces_no_delegation():
    proposal = assess_relevance(
        _signal(materiality=MATERIALITY_THRESHOLD - 0.01), capability_lifecycle="INTEGRATED"
    )
    assert proposal is None


def test_untested_capability_produces_no_delegation():
    """Do not delegate off an untested/unintegrated capability's output --
    even a high-materiality signal must not trigger delegation if the
    capability that produced it has not reached TESTED."""
    proposal = assess_relevance(_signal(), capability_lifecycle="IMPLEMENTED")
    assert proposal is None


def test_no_evidence_refs_produces_no_delegation():
    proposal = assess_relevance(_signal(evidence_refs=[]), capability_lifecycle="INTEGRATED")
    assert proposal is None


def test_unrouted_category_produces_no_delegation():
    proposal = assess_relevance(_signal(category="something_unrouted"), capability_lifecycle="INTEGRATED")
    assert proposal is None


def test_routine_capability_status_finding_does_not_trigger_delegation():
    """DAT.AI's real, current findings are capability-status strings, not
    change-detection signals -- proves the router correctly produces
    nothing when there is no material-change signal to assess (there is no
    RelevanceSignal constructed at all for a routine status report in
    kernel.py, which is the actual mechanism; this test documents that a
    'capability_status' category, if ever synthesized, also would not route)."""
    proposal = assess_relevance(_signal(category="capability_status"), capability_lifecycle="INTEGRATED")
    assert proposal is None


def test_materiality_out_of_range_rejected():
    with pytest.raises(ValueError):
        _signal(materiality=1.5)


def test_materiality_without_basis_rejected():
    with pytest.raises(ValueError):
        RelevanceSignal(
            institution="dat_ai",
            capability_name="zoning_api",
            category="zoning_change",
            materiality=0.9,
            materiality_basis="",
            evidence_refs=["x"],
            parent_mission_id="m",
        )


def test_high_materiality_yields_high_risk_class():
    proposal = assess_relevance(_signal(materiality=0.85), capability_lifecycle="INTEGRATED")
    assert proposal.risk_class.value == "HIGH"
    assert proposal.priority == 1


def test_medium_materiality_yields_medium_risk_class():
    proposal = assess_relevance(_signal(materiality=0.6), capability_lifecycle="INTEGRATED")
    assert proposal.risk_class.value == "MEDIUM"
    assert proposal.priority == 3


def test_delegation_authorizes_analysis_only():
    """NEXUS Federation F2: `authority` is now the closed AuthorityLevel
    enum (authority/model.py), not the free string this router used
    before authority/model.py existed. ANALYSE is the correct value: the
    delegation asks the recipient to interpret already-gathered evidence,
    nothing more."""
    from authority.model import AuthorityLevel

    proposal = assess_relevance(_signal(), capability_lifecycle="INTEGRATED")
    assert "analysis only" in " ".join(proposal.constraints)
    assert proposal.authority == AuthorityLevel.ANALYSE
