"""TEMPORAL tests: ordering/staleness/duplicate behavior through the full
kernel (not just the pure classify_incoming_report function tested in
tests/unit/test_temporal.py)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from state.temporal import STALE_THRESHOLD
from kernel import FederationKernel
from persistence.db import FederationStore
from tests.conftest import make_dat_ai_payload


def test_out_of_order_report_does_not_overwrite_newer_accepted_state(kernel: FederationKernel):
    now = datetime.now(timezone.utc)
    newer = make_dat_ai_payload(cycle_id="c-new", zoning_lifecycle="INTEGRATED", timestamp=now.isoformat())
    older = make_dat_ai_payload(
        cycle_id="c-old",
        zoning_lifecycle="IMPLEMENTED",
        timestamp=(now - timedelta(minutes=10)).isoformat(),
    )

    kernel.ingest_report(newer)
    result = kernel.ingest_report(older)

    assert result.accepted is False
    assert result.temporal_classification == "OUT_OF_ORDER"

    # Registry must still reflect the NEWER state, untouched by the rejected older report.
    current = kernel.store.get_registry_entry("dat_ai")
    caps = {c["capability_name"]: c for c in current["component_states"]}
    assert caps["zoning_api"]["reported_lifecycle"] == "INTEGRATED"


def test_duplicate_cycle_id_is_idempotent_no_new_action(kernel: FederationKernel, store: FederationStore):
    payload = make_dat_ai_payload(cycle_id="same-cycle")
    r1 = kernel.ingest_report(payload)
    r2 = kernel.ingest_report(payload)  # exact same payload, same cycle_id

    assert r1.accepted is True
    assert r2.accepted is True
    assert r2.temporal_classification == "DUPLICATE"
    # No new delegation, no duplicate registry churn -- same entry content.
    assert r2.registry_entry == r1.registry_entry
    # But the attempt IS logged (for observability), twice.
    assert store.count_reports(institution_id="dat_ai") == 2


def test_stale_report_accepted_but_visibly_flagged(kernel: FederationKernel):
    now = datetime.now(timezone.utc)
    stale_ts = (now - STALE_THRESHOLD - timedelta(minutes=5)).isoformat()
    payload = make_dat_ai_payload(cycle_id="c1", timestamp=stale_ts)
    result = kernel.ingest_report(payload)

    assert result.accepted is True
    assert result.temporal_classification == "STALE"
    caps = {c["capability_name"]: c for c in result.registry_entry["component_states"]}
    assert caps["zoning_api"]["executive_state_class"] == "STALE"


def test_clock_skewed_report_rejected(kernel: FederationKernel):
    future_ts = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    payload = make_dat_ai_payload(cycle_id="c1", timestamp=future_ts)
    result = kernel.ingest_report(payload)
    assert result.accepted is False
    assert result.temporal_classification == "CLOCK_SKEW_REJECTED"
