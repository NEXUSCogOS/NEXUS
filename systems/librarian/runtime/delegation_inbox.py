"""Librarian's delegation inbox.

NEW module, NEXUS Federation F3. This is the "minimum real delivery
transport" the mission requires (section 17): Librarian claims delegations
addressed to it by polling the SAME persisted federation store NEXUS
itself writes to (`persistence.db.FederationStore`), using the
`delegation_delivery_log` table (persistence/db.py, F3 addition) for
idempotent claiming.

This deliberately does NOT call anything in `kernel.py` directly, and
NEXUS's kernel never calls anything in this module directly -- the only
coupling between the two institutions is the shared SQLite file, read and
written through each side's own store methods. This preserves the
institutional boundary the mission requires ("do not bypass it with
direct Python function coupling").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from persistence.db import FederationStore  # nexus_federation, shared store
from runtime.research_executor import execute_research_mission

RECIPIENT = "librarian"


def _is_expired(proposal: dict[str, Any], *, now: datetime) -> bool:
    """A delegation with a stated `ttl_deadline` in the past must not be
    executed as if it were still current -- a stale mission executed late
    could report on evidence/context that no longer applies. `ttl_deadline`
    with no value at all (None) never expires."""
    ttl = proposal.get("ttl_deadline")
    if not ttl:
        return False
    try:
        deadline = datetime.fromisoformat(ttl)
    except ValueError:
        return False  # unparseable deadline is not treated as an expiry
    return now > deadline


@dataclass(frozen=True)
class ExecutedDelegation:
    proposal_id: str
    mission_id: str
    objective: str
    report: dict[str, Any]


def poll_and_execute(
    store: FederationStore, *, data_dir: Path | str, now: datetime | None = None
) -> list[ExecutedDelegation]:
    """Claim every pending delegation addressed to 'librarian' on the
    shared federation store, execute each as a real bounded research
    mission, and mark it executed. Returns the list of
    (proposal, resulting report) pairs -- the CALLER is responsible for
    submitting each report to NEXUS's own kernel.ingest_report(), exactly
    mirroring how a real second process/institution would only emit a
    report and never call NEXUS's kernel itself.

    A delegation whose `ttl_deadline` has already passed is claimed (so it
    is never picked up again) but NOT executed as a real research mission
    -- it is recorded as expired and excluded from the returned list.
    """
    now = now or datetime.now(timezone.utc)
    claimed = store.claim_pending_delegations(RECIPIENT)
    executed: list[ExecutedDelegation] = []

    for proposal in claimed:
        if _is_expired(proposal, now=now):
            store.mark_delegation_executed(proposal["proposal_id"], "EXPIRED_TTL_NOT_EXECUTED")
            store.append_observability_event(
                "expired_delegation_not_executed",
                detail=f"proposal_id={proposal['proposal_id']} ttl_deadline={proposal.get('ttl_deadline')}",
                recorded_at=now.isoformat(),
            )
            continue

        report = execute_research_mission(
            mission_id=proposal["mission_id"],
            objective=proposal["objective"],
            query=proposal["objective"],
            data_dir=data_dir,
        )
        report_dict = report.model_dump(mode="json")
        store.mark_delegation_executed(proposal["proposal_id"], report_dict["cycle_id"])
        executed.append(
            ExecutedDelegation(
                proposal_id=proposal["proposal_id"],
                mission_id=proposal["mission_id"],
                objective=proposal["objective"],
                report=report_dict,
            )
        )

    return executed
