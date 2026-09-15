"""News Intelligence's InstitutionalReport builder. NEXUS Federation F7,
mission section 22. Uses the SAME generic contract Librarian/Sentinel
use (`contracts.generic`) -- no News-specific NEXUS parser.
"""

from __future__ import annotations

import sys
from pathlib import Path

FEDERATION_ROOT = str(Path(__file__).resolve().parent.parent / "nexus_federation")
if FEDERATION_ROOT not in sys.path:
    sys.path.insert(0, FEDERATION_ROOT)

from contracts.generic import (
    CapabilityLifecycle,
    CapabilityStatus,
    Confidence,
    OperatingState,
    build_report,
)

from schema import Event


def build_news_report(*, mission_id: str, event: Event, source_health_summaries: list[dict]) -> tuple[dict, dict]:
    """One real Event -> one InstitutionalReport. `operating_state` is
    DEGRADED, never INTEGRATED/OPERATIONAL, until this institution has
    run for real across multiple acquisition cycles with sustained
    source health -- self-reported honestly, per this federation's
    consistent discipline (Sentinel/Librarian never self-promote either)."""

    unavailable_sources = [s for s in source_health_summaries if s.get("status") == "UNAVAILABLE"]
    operating_state = OperatingState.DEGRADED if unavailable_sources else OperatingState.TESTED

    capability_statuses = [
        CapabilityStatus(
            name="event_acquisition",
            lifecycle=CapabilityLifecycle.TESTED,
            confidence=Confidence(value=0.6, basis=f"real RSS acquisition against {len(source_health_summaries)} configured source(s)"),
            evidence_refs=[f"source_health:{s['source_id']}" for s in source_health_summaries] or ["no_sources_configured"],
            detail=f"{len(unavailable_sources)} of {len(source_health_summaries)} sources unavailable this cycle",
        ),
        CapabilityStatus(
            name="entity_resolution",
            lifecycle=CapabilityLifecycle.TESTED,
            confidence=Confidence(value=0.5, basis="deterministic dictionary match against Sentinel companies table + fixed VN province list; word-boundary matched"),
            evidence_refs=[f"entity:{e.surface_form}" for e in event.entities] or ["no_entities_extracted"],
            detail=f"{sum(1 for e in event.entities if e.resolution_state.value=='RESOLVED')} resolved, {sum(1 for e in event.entities if e.resolution_state.value=='UNRESOLVED')} unresolved",
        ),
        CapabilityStatus(
            name="event_construction",
            lifecycle=CapabilityLifecycle.TESTED,
            confidence=Confidence(value=0.5, basis="deterministic keyword-based type classification + rule-based materiality"),
            evidence_refs=event.evidence_refs,
            detail=f"event_type={event.event_type.value}, materiality={event.materiality['score']}",
        ),
    ]

    findings = [
        f"OBSERVED: real item acquired, headline={event.headline_summary!r}",
        f"DERIVED: event_type={event.event_type.value} ({event.materiality['basis']})",
        f"{event.claim_epistemology.value}: source_count={event.source_count}, "
        f"independent_source_count={event.independent_source_count}",
    ]

    limitations = list(event.uncertainty)
    limitations.append(
        "Source set is bounded to 2 configured public RSS feeds "
        "(mission section 6: 'build a small high-quality source set "
        "before broad coverage') -- broader source diversity has not "
        "been established."
    )
    if unavailable_sources:
        limitations.append(
            f"Source(s) unavailable this cycle: {[s['source_id'] for s in unavailable_sources]} "
            f"-- NOT compensated for with any synthetic replacement content."
        )

    report = build_report(
        institution="news_intelligence",
        mission_id=mission_id,
        objective="Acquire, normalize, and report a real external-world event",
        operating_state=operating_state,
        capability_statuses=capability_statuses,
        findings=findings,
        evidence_refs=event.evidence_refs,
        limitations=limitations,
        uncertainty=event.uncertainty,
        provenance_refs=event.provenance_refs,
    )
    # Returned SEPARATELY from the report payload, never embedded inside
    # it: contracts.generic.InstitutionalReport has extra="forbid", so
    # any additional key would fail kernel.ingest_report()'s own
    # validation. Event metadata NEXUS/routing needs is passed alongside
    # the strict report dict, not smuggled inside it.
    event_metadata = {
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "novelty": event.novelty.value,
        "materiality": event.materiality,
        "status": event.status.value,
        "claim_epistemology": event.claim_epistemology.value,
        "freshness": event.freshness,
        "locations": event.locations,
        "entities": [
            {
                "surface_form": e.surface_form,
                "entity_type": e.entity_type.value,
                "canonical_entity": e.canonical_entity,
                "resolution_state": e.resolution_state.value,
            }
            for e in event.entities
        ],
    }
    return report.model_dump(), event_metadata
