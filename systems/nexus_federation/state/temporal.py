"""Temporal semantics for institutional reports.

New module, NEXUS Federation F1 (2026-08-27). Governs whether an incoming
report is CURRENT, STALE, EXPIRED, OUT_OF_ORDER, or a DUPLICATE relative to
whatever NEXUS has already accepted for that institution. No report is ever
accepted or rejected on subjective grounds -- every classification below is
a pure function of two timestamps, a cycle_id comparison, and explicit,
named threshold constants.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum


class TemporalClassification(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    EXPIRED = "EXPIRED"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    DUPLICATE = "DUPLICATE"
    CLOCK_SKEW_REJECTED = "CLOCK_SKEW_REJECTED"


# Named, explicit thresholds -- not magic numbers scattered through logic.
STALE_THRESHOLD = timedelta(hours=1)
EXPIRED_THRESHOLD = timedelta(hours=24)
MAX_CLOCK_SKEW = timedelta(minutes=5)


@dataclass(frozen=True)
class TemporalDecision:
    classification: TemporalClassification
    accept: bool
    reason: str


def _parse(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        raise ValueError(f"timestamp {ts!r} has no timezone; refusing to guess one")
    return dt


def classify_incoming_report(
    *,
    incoming_timestamp: str,
    incoming_cycle_id: str,
    prior_accepted_timestamp: str | None,
    prior_accepted_cycle_id: str | None,
    now: datetime | None = None,
) -> TemporalDecision:
    """The one function that decides whether an incoming report may update
    accepted institutional state, and why.

    Ordering of checks is deliberate: clock skew is checked first (a report
    from the future is suspicious regardless of anything else), then
    duplicate (same cycle_id -- idempotent, not an error), then ordering
    (older timestamp than what is already accepted -- rejected, an older
    report can never overwrite newer accepted state), then staleness of the
    incoming report itself relative to wall-clock now.
    """
    now = now or datetime.now(timezone.utc)
    incoming_dt = _parse(incoming_timestamp)

    if incoming_dt - now > MAX_CLOCK_SKEW:
        return TemporalDecision(
            classification=TemporalClassification.CLOCK_SKEW_REJECTED,
            accept=False,
            reason=(
                f"incoming timestamp {incoming_dt.isoformat()} is "
                f"{(incoming_dt - now)} ahead of NEXUS's clock "
                f"({now.isoformat()}), exceeding MAX_CLOCK_SKEW={MAX_CLOCK_SKEW}"
            ),
        )

    if prior_accepted_cycle_id is not None and incoming_cycle_id == prior_accepted_cycle_id:
        return TemporalDecision(
            classification=TemporalClassification.DUPLICATE,
            accept=True,  # idempotent accept: no new state transition, no new action
            reason=f"cycle_id {incoming_cycle_id!r} already accepted; idempotent no-op",
        )

    if prior_accepted_timestamp is not None:
        prior_dt = _parse(prior_accepted_timestamp)
        if incoming_dt < prior_dt:
            return TemporalDecision(
                classification=TemporalClassification.OUT_OF_ORDER,
                accept=False,
                reason=(
                    f"incoming timestamp {incoming_dt.isoformat()} is older "
                    f"than the currently-accepted {prior_dt.isoformat()}; an "
                    f"older report may never overwrite newer accepted state"
                ),
            )

    age = now - incoming_dt
    if age > EXPIRED_THRESHOLD:
        return TemporalDecision(
            classification=TemporalClassification.EXPIRED,
            accept=True,  # still accepted as the latest state, but flagged
            reason=f"report age {age} exceeds EXPIRED_THRESHOLD={EXPIRED_THRESHOLD}",
        )
    if age > STALE_THRESHOLD:
        return TemporalDecision(
            classification=TemporalClassification.STALE,
            accept=True,
            reason=f"report age {age} exceeds STALE_THRESHOLD={STALE_THRESHOLD}",
        )

    return TemporalDecision(
        classification=TemporalClassification.CURRENT,
        accept=True,
        reason="within staleness threshold, newer than prior accepted state (or first report)",
    )


def classify_age_only(timestamp: str, *, now: datetime | None = None) -> TemporalClassification:
    """Reclassify an already-accepted report's age at query time (not
    ingest time) -- used so state visibly becomes STALE/EXPIRED over time
    without a new report ever arriving, per the requirement that stale
    state remains visible as stale rather than being silently replaced or
    silently treated as still current."""
    now = now or datetime.now(timezone.utc)
    dt = _parse(timestamp)
    age = now - dt
    if age > EXPIRED_THRESHOLD:
        return TemporalClassification.EXPIRED
    if age > STALE_THRESHOLD:
        return TemporalClassification.STALE
    return TemporalClassification.CURRENT
