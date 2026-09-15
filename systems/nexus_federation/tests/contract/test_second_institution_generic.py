"""Second-institution contract-generality test (F2 mission section 14).

This is a CONTRACT-GENERALITY test, not a fake operational subsystem: it
proves `ingress/contract_registry.py`'s dispatch mechanism, and every
downstream kernel module, accept a second institution id with a
completely different schema_version, operating_state vocabulary,
capability-lifecycle vocabulary, and capability names -- WITHOUT any
change to ingress/validator.py, kernel.py, registry/models.py,
state/capability.py, state/executive_state.py, state/temporal.py,
evidence/resolver.py, or relevance/router.py. The only thing added for
this test is a registry ENTRY (register_contract), added and removed by
the test itself, plus the standalone synthetic_fixture.py module that is
never imported by any production module.

No real institution named "test_fixture_institution" exists or is claimed
to exist anywhere in NEXUS.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ingress.contract_registry import register_contract, unregister_contract
from kernel import FederationKernel
from persistence.db import FederationStore
from tests.contract.synthetic_fixture import (
    FIXTURE_INSTITUTION_ID,
    FIXTURE_SCHEMA_VERSION,
    FixtureCapabilityLifecycle,
    FixtureOperatingState,
    validate_fixture_report,
)


@pytest.fixture
def registered_fixture_contract():
    register_contract(
        FIXTURE_INSTITUTION_ID, validate_fixture_report, frozenset({FIXTURE_SCHEMA_VERSION})
    )
    yield
    unregister_contract(FIXTURE_INSTITUTION_ID)


def _fixture_payload(cycle_id="fixture-c1", timestamp=None):
    return {
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "institution": FIXTURE_INSTITUTION_ID,
        "mission_id": "fixture-mission",
        "cycle_id": cycle_id,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "operating_state": FixtureOperatingState.RESEARCH_ACTIVE.value,
        "capability_statuses": [
            {
                "name": "literature_review",  # a capability name DAT.AI has never heard of
                "lifecycle": FixtureCapabilityLifecycle.PEER_REVIEWED.value,
                "evidence_refs": ["some_fixture_evidence_ref.md"],
                "detail": "synthetic test fixture capability",
            },
            {
                "name": "corpus_health",
                "lifecycle": FixtureCapabilityLifecycle.DRAFT.value,
                "evidence_refs": [],
                "detail": "another synthetic capability",
            },
        ],
        "objective": "contract-generality test only",
        "findings": ["literature_review: PEER_REVIEWED"],
        "limitations": [],
        "evidence_refs": ["some_fixture_evidence_ref.md"],
        "provenance_refs": [],
    }


def test_unregistered_institution_fails_closed(kernel: FederationKernel):
    """Before registration, this institution id is correctly rejected --
    proving the registry lookup is real, not a bypass."""
    result = kernel.ingest_report(_fixture_payload())
    assert result.accepted is False
    assert "no registered contract" in result.reason


def test_second_institution_accepted_with_zero_production_code_changes(
    kernel: FederationKernel, registered_fixture_contract
):
    result = kernel.ingest_report(_fixture_payload(cycle_id="fixture-c1"))
    assert result.accepted is True
    assert result.temporal_classification == "CURRENT"

    caps = {c["capability_name"]: c for c in result.registry_entry["component_states"]}
    assert caps["literature_review"]["reported_lifecycle"] == "PEER_REVIEWED"
    assert caps["corpus_health"]["reported_lifecycle"] == "DRAFT"
    # An unrecognized vocabulary degrades gracefully -- it is never treated
    # as CONTRADICTORY on first sighting (no prior state to compare).
    assert caps["literature_review"]["executive_state_class"] in ("DERIVED", "UNKNOWN")


def test_second_institution_coexists_independently_with_dat_ai(
    kernel: FederationKernel, registered_fixture_contract
):
    from tests.conftest import make_dat_ai_payload

    kernel.ingest_report(make_dat_ai_payload(cycle_id="dat-c1"))
    kernel.ingest_report(_fixture_payload(cycle_id="fixture-c1"))

    entries = {e["institution_id"]: e for e in kernel.store.all_registry_entries()}
    assert set(entries.keys()) == {"dat_ai", "test_fixture_institution"}
    assert entries["dat_ai"]["component_states"][0]["capability_name"] == "zoning_api"
    assert entries["test_fixture_institution"]["component_states"][0]["capability_name"] == "literature_review"


def test_second_institution_temporal_ordering_is_independent_of_dat_ai(
    kernel: FederationKernel, registered_fixture_contract
):
    """A stale/out-of-order check for one institution never touches the
    other's state -- proving per-institution isolation, exactly what a
    real second institution needs."""
    from datetime import timedelta

    from tests.conftest import make_dat_ai_payload

    now = datetime.now(timezone.utc)
    kernel.ingest_report(make_dat_ai_payload(cycle_id="dat-c1", timestamp=now.isoformat()))
    kernel.ingest_report(_fixture_payload(cycle_id="fixture-c1", timestamp=now.isoformat()))

    # An out-of-order report for the fixture institution must not affect DAT.AI's state.
    older = (now - timedelta(minutes=10)).isoformat()
    result = kernel.ingest_report(_fixture_payload(cycle_id="fixture-old", timestamp=older))
    assert result.temporal_classification == "OUT_OF_ORDER"

    dat_ai_entry = kernel.store.get_registry_entry("dat_ai")
    assert dat_ai_entry["last_verified_cycle"] == "dat-c1"  # untouched
