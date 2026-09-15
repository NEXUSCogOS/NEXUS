"""Observability counters.

New module, NEXUS Federation F1, extended in F2. Every counter that CAN be
derived from a persisted, append-only log is derived that way -- never a
separately-mutated integer that could drift from what actually happened.
No self-certifying health percentage is computed anywhere here.

Three counters (`process_recoveries`, `crash_recoveries`,
`restart_recovery_duration_seconds`) are the one honest exception: whether
a process was actually killed and restarted, or a crash-point was actually
exercised, is a fact about the outside world that no query over this
store's own tables can determine on its own (a store has no way to know
"was I just reopened by a brand-new OS process" vs. "was I reopened by the
same process for an unrelated reason"). These are recorded explicitly, by
whichever test or operational code actually witnessed the event, into
`observability_event_log` -- see persistence/db.py -- and are counted from
there, not fabricated or estimated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from persistence.db import FederationStore


@dataclass(frozen=True)
class FederationCounters:
    reports_received: int
    reports_accepted: int
    reports_rejected: int
    reports_stale: int
    reports_duplicate: int
    evidence_resolution_failures: int
    delegations_proposed: int
    schema_version_mismatch: int
    # NEXUS Federation F2 additions:
    process_recoveries: int
    crash_recoveries: int
    provenance_resolutions: int
    provenance_failures: int
    evidence_drift_events: int
    state_transitions: int
    dependency_degradations: int
    delegation_idempotency_suppressions: int
    restart_recovery_duration_seconds: Optional[float]


def compute_counters(
    store: FederationStore,
    *,
    evidence_resolution_failure_count: int = 0,
    dependency_degradations: int = 0,
    restart_recovery_duration_seconds: Optional[float] = None,
) -> FederationCounters:
    """`evidence_resolution_failure_count` is passed in rather than queried
    from report_log because evidence resolution happens at ingest time and
    is not itself a per-report persisted count (the per-attempt detail
    lives in evidence_resolution_ledger instead -- see
    `evidence_drift_events`/`provenance_failures` below for what IS derived
    from there). `dependency_degradations` and
    `restart_recovery_duration_seconds` are supplied by whichever code
    actually ran a dependency-graph failure-propagation check or a
    restart-recovery timing measurement (dependency/graph.py,
    tests/restart/) -- neither is inferable from this store's own tables.
    """
    return FederationCounters(
        reports_received=store.count_reports(),
        reports_accepted=store.count_reports(accepted=1),
        reports_rejected=store.count_reports(accepted=0),
        reports_stale=store.count_reports(temporal_classification="STALE")
        + store.count_reports(temporal_classification="EXPIRED"),
        reports_duplicate=store.count_reports(temporal_classification="DUPLICATE"),
        evidence_resolution_failures=evidence_resolution_failure_count,
        delegations_proposed=store.count_delegations(),
        schema_version_mismatch=store.count_reports(temporal_classification="SCHEMA_REJECTED"),
        process_recoveries=store.count_observability_events("process_recovery"),
        crash_recoveries=store.count_observability_events("crash_recovery"),
        provenance_resolutions=store.count_provenance_records(),
        provenance_failures=store.count_evidence_resolutions(verification_result="MISSING")
        + store.count_evidence_resolutions(verification_result="INVALID"),
        evidence_drift_events=store.count_evidence_resolutions(verification_result="INVALID"),
        state_transitions=store.count_state_events(),
        dependency_degradations=dependency_degradations,
        delegation_idempotency_suppressions=store.count_observability_events("delegation_idempotency_suppression"),
        restart_recovery_duration_seconds=restart_recovery_duration_seconds,
    )
