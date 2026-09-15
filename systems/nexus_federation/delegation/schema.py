"""Typed delegation proposal schema.

New module, NEXUS Federation F1, hardened in F2. A delegation proposal is
NEXUS's typed, reproducible output when it decides a finding from one
institution is relevant enough that another institution should be asked to
look at it. Only the proposal object itself is produced -- no recipient
institution is connected, and nothing is actually delivered anywhere.

NEXUS Federation F2 additions:
- `idempotency_key`: deterministic (see delegation/idempotency.py), so the
  persistence layer can enforce "same accepted report + same executive
  rule -> at most one delegation" structurally, not by convention.
- `authority`: a closed AuthorityLevel enum (authority/model.py) instead of
  a free string -- a recipient may not infer broader authority than this
  field states, and this module refuses to construct a proposal above the
  phase ceiling (ANALYSE).
- `resource_budget`: a required, fully-bounded ResourceBudget object
  (budget/schema.py) instead of an optional free-text string -- every
  delegation now carries an explicit, evidenced resource cap.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from authority.model import AuthorityLevel, exceeds_phase_ceiling
from budget.schema import ResourceBudget


class RiskClass(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DelegationProposal(BaseModel):
    """Reproducible from executive-decision evidence: every field here
    traces back either to the triggering InstitutionalReport (evidence_refs,
    reason) or to the relevance router's own deterministic decision logic
    (priority, risk_class, idempotency_key) -- nothing is a free-text human
    judgment call."""

    model_config = ConfigDict(extra="forbid")

    mission_id: str
    issuer: str = "nexus_federation"
    recipient: str  # e.g. "sentinel", "librarian", "news", "youtube" -- not required to be connected
    objective: str
    reason: str
    evidence_refs: list[str] = Field(default_factory=list)
    priority: int  # 1 (highest) .. 5 (lowest), deterministic from the router
    authority: AuthorityLevel = AuthorityLevel.ANALYSE  # the delegation itself asks for analysis, not action
    constraints: list[str] = Field(default_factory=list)
    resource_budget: ResourceBudget
    ttl_deadline: str | None = None
    success_criteria: list[str] = Field(default_factory=list)
    risk_class: RiskClass
    parent_mission: str  # the DAT.AI mission_id/cycle_id that triggered this
    requested_output_contract: str = "InstitutionalReport v1.1.0"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    proposal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    idempotency_key: str  # deterministic; see delegation/idempotency.py -- NOT proposal_id
    provenance_id: str | None = None  # NEXUS Federation F3: the delegation_proposal
    # ProvenanceRecord id created alongside this proposal (kernel.py) -- pass this as
    # `triggering_provenance_ids` when later ingesting the recipient's resulting
    # report, closing the cross-institution provenance chain.

    @model_validator(mode="after")
    def _authority_never_exceeds_phase_ceiling(self):
        if exceeds_phase_ceiling(self.authority):
            raise ValueError(
                f"authority={self.authority!r} exceeds the phase ceiling "
                f"(ANALYSE) -- NEXUS Federation F1/F2 never grants "
                f"generation, modification, architectural, or external "
                f"authority in a delegation"
            )
        return self
