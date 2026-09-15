"""Shared fixtures for nexus_federation tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

# NOTE: make_dat_ai_payload() below builds a DAT.AI-specific InstitutionalReport
# via DAT.AI's OWN institutional contract (institutional.contract), not the
# shared federation-generic one (contracts.generic). ComponentEvidence is a
# DAT.AI-specific concept (database/postgis/migrations/configuration/
# external_storage health) that was never part of the generic contract --
# the generic contract's build_report() instead takes an institution-agnostic
# operating_state + capability_statuses with no component_evidence parameter
# at all. This conftest previously imported ComponentEvidence from
# contracts.generic, which never defined it (ImportError, broke collection
# for 9 test files); the fix is importing from the module that actually
# defines it and whose build_report() signature this payload-builder calls.
from institutional.contract import (
    CapabilityLifecycle,
    CapabilityStatus,
    ComponentEvidence,
    Confidence,
    build_report,
)
from kernel import FederationKernel
from persistence.db import FederationStore


@pytest.fixture
def store(tmp_path) -> FederationStore:
    return FederationStore(tmp_path / "federation_test.db")


@pytest.fixture
def kernel(store: FederationStore) -> FederationKernel:
    return FederationKernel(store)


def make_dat_ai_payload(
    *,
    cycle_id: str = "cycle-1",
    timestamp: str | None = None,
    zoning_lifecycle: CapabilityLifecycle = CapabilityLifecycle.INTEGRATED,
    zoning_evidence_refs: list[str] | None = None,
    database: str = "healthy",
    postgis: str = "healthy",
    migrations: str = "healthy",
    external_storage: str = "available",
    findings: list[str] | None = None,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    """Build a real, schema-valid DAT.AI InstitutionalReport payload for
    testing -- constructed via DAT.AI's own build_report(), never a
    hand-rolled dict, so tests exercise the real contract shape."""
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    report = build_report(
        mission_id="test-mission",
        objective="test objective",
        component_evidence=ComponentEvidence(
            database=database,
            postgis=postgis,
            migrations=migrations,
            configuration="healthy",
            external_storage=external_storage,
        ),
        capability_statuses=[
            CapabilityStatus(
                name="zoning_api",
                lifecycle=zoning_lifecycle,
                confidence=Confidence(value=1.0, basis="test fixture"),
                evidence_refs=zoning_evidence_refs or ["DATAI_CANONICAL_TEST_BASELINE.md"],
            ),
            CapabilityStatus(
                name="valuation",
                lifecycle=CapabilityLifecycle.NOT_COMMISSIONED,
                evidence_refs=["PRESERVED_EVIDENCE_CONCLUSIONS.md"],
            ),
        ],
        findings=findings if findings is not None else ["zoning_api: test finding"],
        evidence_refs=["DATAI_CANONICAL_TEST_BASELINE.md"],
        limitations=limitations or [],
        cycle_id=cycle_id,
    )
    payload = report.model_dump(mode="json")
    payload["timestamp"] = ts  # override to control test timing precisely
    return payload
