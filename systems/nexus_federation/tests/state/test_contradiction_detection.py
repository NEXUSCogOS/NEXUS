"""STATE tests: contradiction detection between successive reports."""

from __future__ import annotations

from datetime import timedelta

from kernel import FederationKernel
from tests.conftest import make_dat_ai_payload


def _later(ts_iso: str, delta: timedelta) -> str:
    from datetime import datetime

    return (datetime.fromisoformat(ts_iso) + delta).isoformat()


def test_unexplained_regression_flagged_contradictory(kernel: FederationKernel):
    first = make_dat_ai_payload(cycle_id="c1", zoning_lifecycle="INTEGRATED")
    r1 = kernel.ingest_report(first)
    t1 = r1.registry_entry["last_report_timestamp"]

    second = make_dat_ai_payload(
        cycle_id="c2",
        zoning_lifecycle="IMPLEMENTED",  # regression on the ladder
        timestamp=_later(t1, timedelta(minutes=1)),
        findings=["something unrelated happened"],  # does NOT mention zoning_api
    )
    r2 = kernel.ingest_report(second)
    caps = {c["capability_name"]: c for c in r2.registry_entry["component_states"]}
    assert caps["zoning_api"]["executive_state_class"] == "CONTRADICTORY"


def test_explained_regression_not_flagged_contradictory(kernel: FederationKernel):
    first = make_dat_ai_payload(cycle_id="c1", zoning_lifecycle="INTEGRATED")
    r1 = kernel.ingest_report(first)
    t1 = r1.registry_entry["last_report_timestamp"]

    second = make_dat_ai_payload(
        cycle_id="c2",
        zoning_lifecycle="IMPLEMENTED",
        timestamp=_later(t1, timedelta(minutes=1)),
        findings=["zoning_api regressed because the database connection was temporarily degraded"],
    )
    r2 = kernel.ingest_report(second)
    caps = {c["capability_name"]: c for c in r2.registry_entry["component_states"]}
    assert caps["zoning_api"]["executive_state_class"] != "CONTRADICTORY"


def test_advancing_lifecycle_never_flagged_contradictory(kernel: FederationKernel):
    first = make_dat_ai_payload(cycle_id="c1", zoning_lifecycle="TESTED")
    r1 = kernel.ingest_report(first)
    t1 = r1.registry_entry["last_report_timestamp"]

    second = make_dat_ai_payload(
        cycle_id="c2",
        zoning_lifecycle="INTEGRATED",  # advance, not regression
        timestamp=_later(t1, timedelta(minutes=1)),
    )
    r2 = kernel.ingest_report(second)
    caps = {c["capability_name"]: c for c in r2.registry_entry["component_states"]}
    assert caps["zoning_api"]["executive_state_class"] != "CONTRADICTORY"
