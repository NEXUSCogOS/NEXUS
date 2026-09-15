"""F10C.1: The one shared specialist-execution boundary.

Structural invariant: NO VALID CLAIM -> NO SPECIALIST EXECUTION.

This is the earliest common point every specialist delivery path (Librarian,
Sentinel, Engineering Studio, DAT.AI, future institutions) should call
through, so the "check claim before executing" guard exists exactly once --
never left to each adapter author's discretion, never duplicated four times.

The F10C duplicate-outcome defect happened because ad-hoc delegation
scripts called store.claim_delegation() and then proceeded regardless of
its return value. claim_and_execute() makes that impossible: the mission
callable is only ever invoked if claim_delegation() returned True.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from persistence.db import FederationStore


@dataclass(frozen=True)
class DeliveryResult:
    """Outcome of one claim_and_execute() call."""
    claimed: bool
    executed: bool
    mission_result: Optional[Any]
    status: str  # "EXECUTED" | "ALREADY_CLAIMED_NO_EXECUTION"


def claim_and_execute(
    store: FederationStore,
    delegation_id: str,
    claimed_by: str,
    mission_fn: Callable[[], Any],
    claim_id: Optional[str] = None,
) -> DeliveryResult:
    """The one shared specialist-execution boundary.

    Attempts the canonical persistent claim. The mission callable
    `mission_fn` is invoked ONLY if the claim was genuinely acquired by
    THIS call -- if the delegation was already claimed (by an earlier
    attempt, a competing worker, or a replay), `mission_fn` is never
    called, no report is produced, no outcome is produced. This is the
    single enforcement point: callers cannot bypass it by forgetting an
    `if not claimed: return` of their own.
    """
    claim_id = claim_id or f"claim-{delegation_id}"
    claimed = store.claim_delegation(
        delegation_id=delegation_id,
        claim_id=claim_id,
        claimed_by=claimed_by,
        claimed_at=datetime.now(timezone.utc).isoformat(),
    )

    if not claimed:
        return DeliveryResult(
            claimed=False, executed=False, mission_result=None,
            status="ALREADY_CLAIMED_NO_EXECUTION",
        )

    result = mission_fn()
    return DeliveryResult(claimed=True, executed=True, mission_result=result, status="EXECUTED")
