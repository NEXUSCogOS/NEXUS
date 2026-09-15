"""NEXUS federation kernel — the orchestrator.

New module, NEXUS Federation F1, hardened in F2. This is the smallest
scientifically defensible executive/federation substrate the mission
asked for: it wires ingress -> temporal classification -> evidence
resolution -> registry update -> (optional) relevance/delegation, all
backed by a persistent SQLite store so a process restart never loses
accepted state.

Deliberately NOT an AGI-like executive kernel: every decision here is a
named, explicit, deterministic function call. Nothing is learned, nothing
is a free-text judgment, nothing self-certifies.

NEXUS Federation F2 hardening:
- The report_log write, the registry upsert, and the state_event rows for
  one accepted cycle are committed in ONE transaction
  (store.commit_accepted_cycle) -- see PROCESS_RECOVERY_PROTOCOL.md for
  why this closes a real crash-point gap that existed in F1's
  three-independent-writes design.
- Every evidence resolution attempt is recorded to an append-only ledger
  (evidence_resolution_ledger), not just the first-seen baseline.
- A structured ProvenanceRecord chain is built and persisted for every
  accepted, non-duplicate cycle: source evidence -> InstitutionalReport ->
  NEXUS executive state -> (if triggered) DelegationProposal.
- Relevance/delegation processing now also runs on the DUPLICATE path
  (idempotency-key-guarded), so a crash after an accepted cycle was
  logged but before its delegation was persisted is recoverable on retry
  without ever producing a second, semantically identical delegation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from delegation.idempotency import compute_idempotency_key
from delegation.schema import DelegationProposal
from evidence.resolver import RESOLVER_VERSION, detect_drift, resolve_evidence_ref
from ingress.validator import ingest_raw_payload
from persistence.db import FederationStore
from provenance.model import ProvenanceRecord, VerificationStatus
from registry.models import InstitutionRegistryEntry
from relevance.router import RelevanceSignal, assess_relevance
from state.capability import ComponentState, lifecycle_rank
from state.executive_state import ExecutiveStateClass
from state.temporal import TemporalClassification, classify_incoming_report


# Descriptive institution_type per registered institution_id -- informational
# only (registry/models.py notes this is "not enforced against a closed
# vocabulary yet"). Was previously an inline `"geospatial_intelligence" if
# institution_id == "dat_ai" else "unknown"` ternary, which meant every
# institution onboarded after DAT.AI (Librarian, F3) was silently recorded
# as "unknown" regardless of its real specialty. Extended, not restructured,
# for NEXUS Federation F5 (Sentinel).
INSTITUTION_TYPES: dict[str, str] = {
    "dat_ai": "geospatial_intelligence",
    "librarian": "academic_research",
    "sentinel": "financial_intelligence",
    "news_intelligence": "external_world_intelligence",
    # NEXUS Federation F8: YouTube Production is a PRODUCTION institution,
    # not an intelligence/truth-source institution -- it consumes
    # evidence from the others, it does not originate world/academic/
    # financial/geospatial truth. authority_ceiling=GENERATE_INTERNAL,
    # publication_authority=NOT_GRANTED (see YOUTUBE_INSTITUTIONAL_CONTRACT.md).
    "youtube_production": "media_production",
}


@dataclass
class KernelResult:
    accepted: bool
    reason: str
    temporal_classification: Optional[str] = None
    registry_entry: Optional[dict[str, Any]] = None
    delegations: list[dict[str, Any]] = field(default_factory=list)
    delegations_suppressed_as_duplicate: int = 0
    evidence_resolution_failures: int = 0
    # One nexus_executive_state ProvenanceRecord id per capability, in
    # report.capability_statuses order -- pass any of these to
    # provenance.graph.trace_back()/explain() to answer "why does this
    # executive state exist?" (NEXUS Federation F2).
    provenance_ids: list[str] = field(default_factory=list)


class FederationKernel:
    def __init__(self, store: FederationStore):
        self.store = store

    # ---- the one public entry point -------------------------------------

    def ingest_report(
        self,
        raw_payload: dict[str, Any],
        *,
        relevance_signals: list[RelevanceSignal] | None = None,
        now: datetime | None = None,
        triggering_provenance_ids: list[str] | None = None,
    ) -> KernelResult:
        """`triggering_provenance_ids` (NEXUS Federation F3): when this
        report is the RESULT of an earlier delegation (e.g. Librarian
        reporting back on a NEXUS-issued research request), pass the
        delegation's own ProvenanceRecord id(s) here -- they become
        additional parents of this report's `institutional_report`-level
        provenance record, closing the cross-institution chain: DAT.AI
        evidence -> DAT.AI finding -> NEXUS state -> delegation ->
        Librarian's own evidence -> Librarian's InstitutionalReport ->
        NEXUS executive state. See CROSS_INSTITUTION_PROVENANCE section of
        NEXUS_LIBRARIAN_DELEGATION_E2E_EVIDENCE.md for the real, executed
        proof."""
        now = now or datetime.now(timezone.utc)

        # 1. schema/version validation -- consumes the institution's own
        # contract directly. This is a single-table write (report_log
        # only); a crash here or before it leaves nothing partially
        # committed anywhere.
        ingress_result = ingest_raw_payload(raw_payload)
        if not ingress_result.accepted:
            self.store.append_report_log(
                institution_id=str(raw_payload.get("institution", "unknown")),
                cycle_id=str(raw_payload.get("cycle_id", "unknown")),
                report_timestamp=str(raw_payload.get("timestamp", now.isoformat())),
                received_at=now.isoformat(),
                temporal_classification="SCHEMA_REJECTED",
                accepted=False,
                reason=ingress_result.reason,
                report_json=raw_payload,
            )
            return KernelResult(accepted=False, reason=ingress_result.reason, temporal_classification="SCHEMA_REJECTED")

        report = ingress_result.report
        institution_id = report.institution
        cycle_id = report.cycle_id

        # 2. temporal classification against prior accepted state
        prior = self.store.last_accepted_report(institution_id)
        prior_timestamp = prior["report_timestamp"] if prior else None
        prior_cycle_id = prior["cycle_id"] if prior else None

        decision = classify_incoming_report(
            incoming_timestamp=report.timestamp,
            incoming_cycle_id=cycle_id,
            prior_accepted_timestamp=prior_timestamp,
            prior_accepted_cycle_id=prior_cycle_id,
            now=now,
        )

        if not decision.accept:
            # Single-table write; rejected reports never touch the registry.
            self.store.append_report_log(
                institution_id=institution_id,
                cycle_id=cycle_id,
                report_timestamp=report.timestamp,
                received_at=now.isoformat(),
                temporal_classification=decision.classification.value,
                accepted=False,
                reason=decision.reason,
                report_json=report.model_dump(mode="json"),
            )
            return KernelResult(
                accepted=False,
                reason=decision.reason,
                temporal_classification=decision.classification.value,
            )

        if decision.classification == TemporalClassification.DUPLICATE:
            # Log the duplicate attempt (single-table, safe), but do NOT
            # re-run evidence resolution or touch the registry/state-event
            # tables -- idempotent no-op for canonical state. Relevance/
            # delegation IS re-attempted here (idempotency-key-guarded):
            # this is what makes a crash between "cycle accepted" and
            # "delegation persisted" recoverable on retry without ever
            # producing a duplicate delegation. See PROCESS_RECOVERY_PROTOCOL.md.
            self.store.append_report_log(
                institution_id=institution_id,
                cycle_id=cycle_id,
                report_timestamp=report.timestamp,
                received_at=now.isoformat(),
                temporal_classification=decision.classification.value,
                accepted=True,
                reason=decision.reason,
                report_json=report.model_dump(mode="json"),
            )
            existing = self.store.get_registry_entry(institution_id)
            delegations, suppressed = self._process_relevance(report, relevance_signals, now=now)
            return KernelResult(
                accepted=True,
                reason=decision.reason,
                temporal_classification=decision.classification.value,
                registry_entry=existing,
                delegations=delegations,
                delegations_suppressed_as_duplicate=suppressed,
            )

        # 3. evidence resolution (per capability, plus report-level refs).
        # All of this is either read-only or writes to additive,
        # attempt-scoped audit tables (evidence_baseline, the evidence
        # resolution ledger, provenance records) -- none of it is the
        # "canonical current state" whose partial-write would be a
        # problem, so it is safe to redo in full if a crash forces a retry
        # before the atomic commit below.
        evidence_failures = 0
        component_states: list[ComponentState] = []
        state_events: list[dict[str, Any]] = []
        report_provenance_ids: list[str] = []
        capability_provenance_ids: dict[str, str] = {}
        prior_entry = self.store.get_registry_entry(institution_id)
        prior_components = {
            c["capability_name"]: c for c in (prior_entry or {}).get("component_states", [])
        }

        for cap in report.capability_statuses:
            resolutions = [resolve_evidence_ref(ref) for ref in cap.evidence_refs]
            unresolved = [r.ref for r in resolutions if not r.resolved]
            evidence_failures += len(unresolved)

            cap_provenance_ids: list[str] = []
            for r in resolutions:
                baseline = self.store.get_evidence_baseline(institution_id, r.ref) if r.resolved else None
                drift = detect_drift(r, baseline) if r.resolved else None

                if not r.resolved:
                    verification_result = VerificationStatus.MISSING
                elif drift is not None:
                    verification_result = VerificationStatus.INVALID
                elif baseline is None:
                    verification_result = VerificationStatus.PARTIAL
                else:
                    verification_result = VerificationStatus.VERIFIED

                self.store.append_evidence_resolution(
                    resolution_id=_new_id(),
                    timestamp=now.isoformat(),
                    institution=institution_id,
                    mission_id=report.mission_id,
                    cycle_id=cycle_id,
                    evidence_ref=r.ref,
                    expected_hash=baseline,
                    observed_hash=r.sha256,
                    existence=r.resolved,
                    verification_result=verification_result.value,
                    reason=drift or r.reason,
                    resolver_version=RESOLVER_VERSION,
                )

                if r.resolved and baseline is None:
                    self.store.set_evidence_baseline_if_absent(
                        institution_id, r.ref, r.sha256, now.isoformat()
                    )

                prov = ProvenanceRecord(
                    source_type="source_evidence_file",
                    source_uri_or_path=r.resolved_path,
                    source_hash=r.sha256,
                    ingestion_timestamp=now.isoformat(),
                    producer=institution_id,
                    method="sha256 file hash via evidence.resolver.resolve_evidence_ref",
                    verification_status=verification_result,
                    verification_method="filesystem existence + sha256 baseline comparison" if verification_result != VerificationStatus.MISSING else None,
                )
                self.store.append_provenance_record(prov.model_dump(mode="json"))
                cap_provenance_ids.append(prov.provenance_id)

            evidence_resolved = len(unresolved) == 0

            prior_component = prior_components.get(cap.name)
            contradictory = self._is_contradictory(
                new_lifecycle=cap.lifecycle.value,
                prior_component=prior_component,
                findings=report.findings,
                limitations=report.limitations,
                capability_name=cap.name,
            )

            if contradictory:
                exec_class = ExecutiveStateClass.CONTRADICTORY
            elif not evidence_resolved:
                exec_class = ExecutiveStateClass.UNKNOWN
            else:
                exec_class = ExecutiveStateClass.DERIVED

            if decision.classification in (TemporalClassification.STALE, TemporalClassification.EXPIRED):
                exec_class = ExecutiveStateClass.STALE

            # Provenance: InstitutionalReport level (one per capability
            # claim, parented on that capability's evidence), then NEXUS
            # executive-state level parented on the report-level record.
            # Honest limitation: DAT.AI does not yet expose its own
            # internal ingestion/spatial-entity/finding-level provenance
            # across the federation boundary, so this chain begins at the
            # evidence artifact NEXUS can itself see -- not at DAT.AI's
            # internal pipeline. See PROVENANCE_GRAPH_SPEC.md LIMITATIONS.
            report_prov = ProvenanceRecord(
                source_type="institutional_report",
                source_uri_or_path=None,
                ingestion_timestamp=now.isoformat(),
                producer=institution_id,
                method="nexus_federation.ingress.ingest_raw_payload",
                parent_provenance_ids=list(cap_provenance_ids) + list(triggering_provenance_ids or []),
                verification_status=VerificationStatus.VERIFIED if evidence_resolved else VerificationStatus.PARTIAL,
                verification_method="pydantic schema validation against institutional.contract.InstitutionalReport",
            )
            self.store.append_provenance_record(report_prov.model_dump(mode="json"))

            exec_state_prov = ProvenanceRecord(
                source_type="nexus_executive_state",
                ingestion_timestamp=now.isoformat(),
                producer="nexus_federation",
                method="state.executive_state derivation from evidence resolution + temporal classification",
                parent_provenance_ids=[report_prov.provenance_id],
                verification_status=VerificationStatus.VERIFIED if exec_class == ExecutiveStateClass.DERIVED else VerificationStatus.PARTIAL,
                verification_method="kernel.FederationKernel.ingest_report deterministic derivation",
            )
            self.store.append_provenance_record(exec_state_prov.model_dump(mode="json"))
            report_provenance_ids.append(exec_state_prov.provenance_id)
            capability_provenance_ids[cap.name] = exec_state_prov.provenance_id

            prior_lifecycle = prior_component.get("reported_lifecycle") if prior_component else None
            state_events.append(
                {
                    "institution_id": institution_id,
                    "capability_name": cap.name,
                    "cycle_id": cycle_id,
                    "prior_lifecycle": prior_lifecycle,
                    "new_lifecycle": cap.lifecycle.value,
                    "executive_state_class": exec_class.value,
                    "temporal_classification": decision.classification.value,
                    "transition_reason": (
                        "contradictory regression, unexplained by findings/limitations" if contradictory
                        else "evidence unresolved" if not evidence_resolved
                        else f"accepted report classified {decision.classification.value}"
                    ),
                    "evidence_refs": list(cap.evidence_refs),
                    "recorded_at": now.isoformat(),
                }
            )

            component_states.append(
                ComponentState(
                    capability_name=cap.name,
                    reported_lifecycle=cap.lifecycle.value,
                    executive_state_class=exec_class,
                    evidence_refs=list(cap.evidence_refs),
                    evidence_resolved=evidence_resolved,
                    unresolved_evidence_refs=unresolved,
                    last_updated_cycle=cycle_id,
                    last_updated_timestamp=report.timestamp,
                    temporal_classification=decision.classification,
                    detail=cap.detail,
                )
            )

        # 4. registry entry -- derived entirely from accepted evidence
        entry = InstitutionRegistryEntry(
            institution_id=institution_id,
            institution_type=INSTITUTION_TYPES.get(institution_id, "unknown"),
            canonical_path=f"systems/{institution_id}",
            contract_version=report.schema_version,
            maturity=report.operating_state.value,
            last_report_timestamp=report.timestamp,
            last_verified_cycle=cycle_id,
            component_states=component_states,
            evidence_refs=list(report.evidence_refs),
            registered_at=(prior_entry or {}).get("registered_at", now.isoformat()),
        )

        # 5. ATOMIC commit: report_log + registry + state_events together.
        # See PROCESS_RECOVERY_PROTOCOL.md for exactly which crash-point
        # gap this closes relative to F1's three-independent-writes design.
        self.store.commit_accepted_cycle(
            report_log_row={
                "institution_id": institution_id,
                "cycle_id": cycle_id,
                "report_timestamp": report.timestamp,
                "received_at": now.isoformat(),
                "temporal_classification": decision.classification.value,
                "accepted": True,
                "reason": decision.reason,
                "report_json": report.model_dump(mode="json"),
            },
            registry_institution_id=institution_id,
            registry_entry=entry.model_dump(mode="json"),
            registry_updated_at=now.isoformat(),
            state_events=state_events,
        )

        # 6. relevance / delegation -- only for explicitly-supplied signals
        # (DAT.AI does not yet emit structured change-detection signals,
        # so nothing is auto-derived from free-text findings here).
        delegations, suppressed = self._process_relevance(
            report, relevance_signals, capability_provenance_ids=capability_provenance_ids, now=now
        )

        return KernelResult(
            accepted=True,
            reason=decision.reason,
            temporal_classification=decision.classification.value,
            registry_entry=entry.model_dump(mode="json"),
            delegations=delegations,
            delegations_suppressed_as_duplicate=suppressed,
            evidence_resolution_failures=evidence_failures,
            provenance_ids=report_provenance_ids,
        )

    # ---- relevance/delegation, idempotency-guarded -----------------------

    def _process_relevance(
        self,
        report: Any,
        relevance_signals: list[RelevanceSignal] | None,
        *,
        capability_provenance_ids: Optional[dict[str, str]] = None,
        now: Optional[datetime] = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Idempotency-key-guarded: safe to call twice (e.g. once on the
        original accept, once more on a later DUPLICATE replay after a
        crash) without ever creating a second delegation for the same
        (institution, cycle, capability, category).

        `capability_provenance_ids` (capability_name -> nexus_executive_state
        ProvenanceRecord id), when available, closes the final hop of the
        provenance chain: a DelegationProposal's own ProvenanceRecord is
        parented on the executive-state record that triggered it. On the
        DUPLICATE replay path this mapping isn't recomputed (no evidence
        re-resolution happens there), so the delegation's provenance record
        is simply parentless in that case -- an honest, stated gap, not a
        fabricated link.
        """
        now = now or datetime.now(timezone.utc)
        capability_provenance_ids = capability_provenance_ids or {}
        delegations: list[dict[str, Any]] = []
        suppressed = 0
        for signal in relevance_signals or []:
            matching_cap = next(
                (c for c in report.capability_statuses if c.name == signal.capability_name), None
            )
            if matching_cap is None:
                continue
            proposal: Optional[DelegationProposal] = assess_relevance(
                signal, capability_lifecycle=matching_cap.lifecycle.value
            )
            if proposal is None:
                continue

            # Build the delegation's own ProvenanceRecord BEFORE persisting
            # the proposal, so its id can be embedded in the proposal
            # itself (proposal.provenance_id) -- this is what lets a later
            # ingest of the recipient's resulting report pass
            # triggering_provenance_ids=[proposal["provenance_id"]] and
            # close the cross-institution chain.
            parent = capability_provenance_ids.get(signal.capability_name)
            delegation_prov = ProvenanceRecord(
                source_type="delegation_proposal",
                ingestion_timestamp=now.isoformat(),
                producer="nexus_federation.relevance_router",
                method="relevance.router.assess_relevance deterministic rule evaluation",
                parent_provenance_ids=[parent] if parent else [],
                verification_status=VerificationStatus.VERIFIED,
                verification_method="deterministic rule evaluation, not independently re-checked",
            )
            proposal = proposal.model_copy(update={"provenance_id": delegation_prov.provenance_id})

            inserted = self.store.append_delegation(proposal.model_dump(mode="json"))
            if inserted:
                delegations.append(proposal.model_dump(mode="json"))
                self.store.append_provenance_record(delegation_prov.model_dump(mode="json"))
            else:
                suppressed += 1
                self.store.append_observability_event(
                    "delegation_idempotency_suppression",
                    detail=f"idempotency_key={proposal.idempotency_key} recipient={proposal.recipient}",
                    recorded_at=now.isoformat(),
                )
        return delegations, suppressed

    @staticmethod
    def _is_contradictory(
        *,
        new_lifecycle: str,
        prior_component: Optional[dict[str, Any]],
        findings: list[str],
        limitations: list[str],
        capability_name: str,
    ) -> bool:
        """A capability regressing on the maturity ladder without any
        finding/limitation mentioning it by name is flagged CONTRADICTORY
        rather than silently accepted as a normal update."""
        if prior_component is None:
            return False
        prior_lifecycle = prior_component.get("reported_lifecycle")
        new_rank = lifecycle_rank(new_lifecycle)
        prior_rank = lifecycle_rank(prior_lifecycle) if prior_lifecycle else None
        if new_rank is None or prior_rank is None:
            return False
        if new_rank >= prior_rank:
            return False
        explained = any(capability_name in text for text in (findings + limitations))
        return not explained


def _new_id() -> str:
    import uuid

    return str(uuid.uuid4())
