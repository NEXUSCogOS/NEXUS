"""Full real end-to-end cross-institution loop:

DAT.AI report -> NEXUS ingest -> delegation to Librarian -> Librarian
executes real research -> Librarian InstitutionalReport -> NEXUS ingest
-> cross-institution provenance chain resolves.

Requires dat_ai AND nexus_federation on PYTHONPATH alongside librarian --
see NEXUS_LIBRARIAN_DELEGATION_E2E_EVIDENCE.md for the real captured
output this test formalizes.
"""

from __future__ import annotations

import pytest

institutional_contract = pytest.importorskip(
    "institutional.contract", reason="requires dat_ai on PYTHONPATH"
)

from institutional.contract import (  # noqa: E402
    CapabilityLifecycle,
    CapabilityStatus,
    ComponentEvidence,
    Confidence,
    build_report,
)
from kernel import FederationKernel  # noqa: E402
from persistence.db import FederationStore  # noqa: E402
from provenance.graph import make_store_lookup, trace_back  # noqa: E402
from relevance.router import RelevanceSignal  # noqa: E402
from runtime.delegation_inbox import poll_and_execute  # noqa: E402


def _dat_ai_payload(cycle_id="dat-ai-cycle-1"):
    report = build_report(
        mission_id="dat-ai-mission-1",
        objective="Zoning classification review",
        component_evidence=ComponentEvidence(database="healthy", postgis="healthy", migrations="healthy", configuration="healthy"),
        capability_statuses=[
            CapabilityStatus(
                name="zoning_api", lifecycle=CapabilityLifecycle.INTEGRATED,
                confidence=Confidence(value=1.0, basis="e2e test"),
                evidence_refs=["DATAI_CANONICAL_TEST_BASELINE.md"],
            ),
        ],
        findings=["zoning_api: land-use reclassification detected requiring research support"],
        evidence_refs=["DATAI_CANONICAL_TEST_BASELINE.md"],
        cycle_id=cycle_id,
    )
    return report.model_dump(mode="json")


def test_full_cross_institution_loop(tmp_path, real_data_dir):
    store = FederationStore(tmp_path / "e2e.db")
    kernel = FederationKernel(store)

    signal = RelevanceSignal(
        institution="dat_ai", capability_name="zoning_api", category="research_request",
        materiality=0.9,
        materiality_basis="ingestion provenance dedup chunk research support for DAT.AI zoning findings",
        evidence_refs=["DATAI_CANONICAL_TEST_BASELINE.md"],
        parent_mission_id="dat-ai-cycle-1",
    )

    # 1. DAT.AI report ingested, delegation to Librarian created.
    r1 = kernel.ingest_report(_dat_ai_payload(), relevance_signals=[signal])
    assert r1.accepted is True
    assert len(r1.delegations) == 1
    delegation = r1.delegations[0]
    assert delegation["recipient"] == "librarian"
    assert delegation["authority"] in ("ANALYSE", "RESEARCH")
    assert delegation["provenance_id"] is not None

    # 2. Librarian claims and executes the real research mission.
    executed = poll_and_execute(store, data_dir=real_data_dir)
    assert len(executed) == 1
    librarian_report = executed[0].report
    assert librarian_report["institution"] == "librarian"

    # 3. NEXUS ingests Librarian's report, linking provenance to the delegation.
    r2 = kernel.ingest_report(
        librarian_report, triggering_provenance_ids=[delegation["provenance_id"]]
    )
    assert r2.accepted is True

    # 4. Both institutions now independently registered.
    entries = {e["institution_id"]: e for e in store.all_registry_entries()}
    assert set(entries.keys()) == {"dat_ai", "librarian"}

    # 5. Cross-institution provenance resolves end-to-end.
    lookup = make_store_lookup(store)
    chain = trace_back(r2.provenance_ids[0], lookup)
    source_types = [rec.source_type for rec in chain]
    assert "delegation_proposal" in source_types  # "why was this requested?"
    assert source_types.count("source_evidence_file") >= 1  # "what evidence supports this?"
    assert source_types[-1] == "nexus_executive_state"  # ends at the final state


def test_duplicate_delegation_across_restart_still_executes_once(tmp_path, real_data_dir):
    db_path = tmp_path / "e2e_restart.db"
    store1 = FederationStore(db_path)
    kernel1 = FederationKernel(store1)

    signal = RelevanceSignal(
        institution="dat_ai", capability_name="zoning_api", category="research_request",
        materiality=0.9, materiality_basis="ingestion provenance dedup chunk",
        evidence_refs=["DATAI_CANONICAL_TEST_BASELINE.md"], parent_mission_id="dat-ai-cycle-1",
    )
    kernel1.ingest_report(_dat_ai_payload(), relevance_signals=[signal])

    # "restart": brand-new store/kernel, same file
    store2 = FederationStore(db_path)
    executed = poll_and_execute(store2, data_dir=real_data_dir)
    assert len(executed) == 1

    # Duplicate ingest of the SAME dat_ai cycle after restart must not
    # produce a second delegation, and re-polling must not re-execute.
    kernel2 = FederationKernel(store2)
    kernel2.ingest_report(_dat_ai_payload(), relevance_signals=[signal])
    assert store2.count_delegations() == 1
    assert poll_and_execute(store2, data_dir=real_data_dir) == []
