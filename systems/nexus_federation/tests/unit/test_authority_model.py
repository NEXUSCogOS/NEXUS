"""Federation authority taxonomy tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from authority.model import AuthorityLevel, MAX_GRANTABLE_AUTHORITY_THIS_PHASE, exceeds_phase_ceiling
from budget.schema import DEFAULT_ANALYSIS_ONLY_BUDGET
from delegation.schema import DelegationProposal, RiskClass


def _base_kwargs(**overrides):
    kwargs = dict(
        mission_id="m",
        recipient="sentinel",
        objective="o",
        reason="r",
        priority=1,
        resource_budget=DEFAULT_ANALYSIS_ONLY_BUDGET,
        risk_class=RiskClass.LOW,
        parent_mission="m",
        idempotency_key="k",
    )
    kwargs.update(overrides)
    return kwargs


def test_max_ceiling_is_generate_internal():
    """NEXUS Federation F8: deliberately, visibly raised one rung from
    ANALYSE to GENERATE_INTERNAL, so YouTube Production (the first
    institution asked to produce a durable internal artifact rather than
    only research/analysis) can be delegated to at all. See
    authority/model.py's own comment on this exact change."""
    assert MAX_GRANTABLE_AUTHORITY_THIS_PHASE == AuthorityLevel.GENERATE_INTERNAL


@pytest.mark.parametrize(
    "level",
    [AuthorityLevel.OBSERVE, AuthorityLevel.RESEARCH, AuthorityLevel.ANALYSE, AuthorityLevel.GENERATE_INTERNAL],
)
def test_levels_at_or_below_ceiling_do_not_exceed(level):
    assert exceeds_phase_ceiling(level) is False


@pytest.mark.parametrize(
    "level",
    [
        AuthorityLevel.MODIFY_REVERSIBLE,
        AuthorityLevel.ARCHITECTURAL_CHANGE,
        AuthorityLevel.EXTERNAL_ACTION,
        AuthorityLevel.HIGH_CONSEQUENCE_ACTION,
    ],
)
def test_levels_above_ceiling_exceed(level):
    assert exceeds_phase_ceiling(level) is True


def test_delegation_proposal_defaults_to_analyse():
    proposal = DelegationProposal(**_base_kwargs())
    assert proposal.authority == AuthorityLevel.ANALYSE


@pytest.mark.parametrize(
    "level",
    [
        AuthorityLevel.MODIFY_REVERSIBLE,
        AuthorityLevel.ARCHITECTURAL_CHANGE,
        AuthorityLevel.EXTERNAL_ACTION,
        AuthorityLevel.HIGH_CONSEQUENCE_ACTION,
    ],
)
def test_delegation_proposal_refuses_authority_above_ceiling(level):
    """Structural enforcement: constructing a DelegationProposal with an
    authority above GENERATE_INTERNAL is impossible, not merely
    discouraged."""
    with pytest.raises(ValidationError):
        DelegationProposal(**_base_kwargs(authority=level))


def test_delegation_proposal_accepts_generate_internal():
    """NEXUS Federation F8: GENERATE_INTERNAL is now grantable -- this is
    the authority level youtube_production delegations actually use."""
    proposal = DelegationProposal(**_base_kwargs(authority=AuthorityLevel.GENERATE_INTERNAL))
    assert proposal.authority == AuthorityLevel.GENERATE_INTERNAL


def test_a_recipient_cannot_infer_broader_authority_from_objective_text():
    """The mission's explicit instruction: authority is stated, not
    inferable. A dramatic-sounding objective does not change the granted
    authority field."""
    proposal = DelegationProposal(
        **_base_kwargs(objective="Take over the financial system and execute all trades immediately")
    )
    assert proposal.authority == AuthorityLevel.ANALYSE
