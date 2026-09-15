"""NEXUS Executive Coordinator.

F9 composition layer. Wraps the canonical FederationKernel without
duplicating its responsibilities.

Adds executive cognition:
- attention assessment
- priority assignment
- mission planning
- dependency scheduling
- resource governance
- outcome evaluation
- retry decisions
- escalation
- autonomous orchestration

All persistent actions delegate to the canonical FederationKernel +
FederationStore. No duplicate state stores.

Architecture:

ExecutiveCoordinator (this module)
    ↓
canonical FederationKernel (kernel.py)
    ↓
canonical FederationStore (persistence/db.py)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from kernel import FederationKernel, KernelResult
from persistence.db import FederationStore
from executive.attention import AttentionFactors, AttentionSignal, compute_attention_score
from executive.priority import PriorityFactors, PriorityDecision
from executive.mission_state import MissionState, validate_transition, is_terminal
from executive.dependency_semantics import DependencyType, detect_cycle
from executive.scheduler import ExecutiveScheduler
from executive.capacity import AvailabilityState, CircuitState, is_admissible


class ExecutiveCoordinator:
    """Composition layer that wraps the canonical federation kernel.

    Does NOT create its own:
    - delegation store
    - evidence store
    - mission database
    - provenance store
    - institution registry
    - state persistence

    All persistent operations flow through self.kernel.
    """

    def __init__(self, store: FederationStore):
        """Initialize coordinator with a canonical federation kernel.

        Args:
            store: The shared FederationStore (not created here).
        """
        self.kernel = FederationKernel(store)
        self.store = store
        self._policy_version = "F9.0"
        self.scheduler = ExecutiveScheduler(self)

    # -------- Phase A: Attention + Priority Assessment --------

    def assess_attention(self, signal: AttentionSignal) -> tuple[bool, str]:
        """Assess whether an incoming signal warrants executive attention.

        PHASE A: no persistence changes. Pure deterministic assessment.

        Returns (accept, reason).
        """
        score = compute_attention_score(signal.factors)
        attention_class = signal.attention_class

        # Minimal: likely routine, not a signal.
        if attention_class.value == "MINIMAL":
            return False, f"LOW_ATTENTION_SCORE ({score:.2f})"

        # Critical/High/Normal: deserves further consideration.
        if attention_class.value in ("CRITICAL", "HIGH", "NORMAL"):
            return True, f"{attention_class.value}_ATTENTION ({score:.2f})"

        # Low: can queue, but not urgent.
        if attention_class.value == "LOW":
            return True, f"LOW_ATTENTION_DEFERRED ({score:.2f})"

        return False, f"UNKNOWN_ATTENTION_CLASS ({attention_class})"

    def assign_priority(
        self,
        mission_id: str,
        factors: PriorityFactors,
        basis: str,
        now: Optional[datetime] = None,
    ) -> PriorityDecision:
        """Assign priority to a mission based on explicit factors.

        PHASE A: no persistence changes. Pure deterministic assignment.

        Returns PriorityDecision.
        """
        return PriorityDecision.from_factors(
            mission_id=mission_id,
            factors=factors,
            basis=basis,
            now=now,
        )

    # -------- Phase D: Institution Capacity + Resource Governance --------

    def get_institution_capacity(self, institution_id: str) -> Optional[dict[str, Any]]:
        """Get capacity state for an institution."""
        return self.store.get_institution_capacity(institution_id)

    def update_institution_capacity(self, institution_id: str, capacity: dict[str, Any]) -> None:
        """Update institution capacity state."""
        self.store.upsert_institution_capacity(institution_id, capacity)

    def is_institution_admissible(self, institution_id: str) -> bool:
        """True if institution can accept new missions."""
        capacity = self.get_institution_capacity(institution_id)
        return is_admissible(capacity)

    # -------- Phase C: Dependencies + Scheduling --------

    def record_dependency(
        self,
        mission_id: str,
        depends_on_mission_id: str,
        dependency_type: str,
        reason: str,
    ) -> tuple[bool, str]:
        """Record a mission dependency."""
        import uuid
        from executive.dependency_semantics import validate_dependency_type

        if not validate_dependency_type(dependency_type):
            return False, f"invalid dependency type: {dependency_type}"

        dependency_id = str(uuid.uuid4())
        try:
            self.store.record_dependency(
                dependency_id=dependency_id,
                mission_id=mission_id,
                depends_on_mission_id=depends_on_mission_id,
                dependency_type=dependency_type,
                reason=reason,
                policy_version=self._policy_version,
            )
            return True, f"dependency recorded: {mission_id} {dependency_type} {depends_on_mission_id}"
        except Exception as e:
            return False, f"persistence error: {e}"

    def select_next_mission(self) -> Optional[str]:
        """Get the next mission to run (if any)."""
        return self.scheduler.select_next_mission()

    # -------- Phase B: Mission Lifecycle Persistence --------

    def transition_mission(
        self,
        delegation_id: str,
        to_state: MissionState,
        reason: str,
        actor: str = "nexus",
        evidence_refs: Optional[list[str]] = None,
        lease_id: Optional[str] = None,
        retry_count: Optional[int] = None,
    ) -> tuple[bool, str]:
        """Transition a mission to a new state.

        Validates the transition against the state machine, then persists it
        to FederationStore. Returns (success, reason).

        All state changes flow through here; no in-memory mutations.
        """
        import uuid
        from executive.mission_state import MissionState as MS

        # Get current state
        current_state_str = self.store.get_mission_state(delegation_id)
        current_state = MS(current_state_str) if current_state_str else None

        # Validate transition
        valid, validation_reason = validate_transition(current_state, to_state)
        if not valid:
            return False, validation_reason

        # Persist transition
        event_id = str(uuid.uuid4())
        try:
            self.store.record_mission_transition(
                event_id=event_id,
                delegation_id=delegation_id,
                previous_state=current_state_str if current_state else None,
                new_state=to_state.value,
                reason=reason,
                actor=actor,
                policy_version=self._policy_version,
                evidence_refs=evidence_refs,
                lease_id=lease_id,
                retry_count=retry_count,
            )
            return True, f"transitioned to {to_state.value}"
        except Exception as e:
            return False, f"persistence error: {e}"

    def get_mission_state(self, delegation_id: str) -> Optional[str]:
        """Get the current state of a mission."""
        return self.store.get_mission_state(delegation_id)

    def get_mission_history(self, delegation_id: str) -> list[dict[str, Any]]:
        """Get full lifecycle history for a mission."""
        return self.store.get_mission_history(delegation_id)

    def list_missions_by_state(self, state: str) -> list[str]:
        """List all delegation_ids in a given state."""
        return self.store.list_missions_by_state(state)

    # -------- Delegation to Canonical Kernel --------

    def ingest_report(
        self,
        raw_payload: dict[str, Any],
        *,
        relevance_signals=None,
        now: Optional[datetime] = None,
        triggering_provenance_ids=None,
    ) -> KernelResult:
        """Ingest an institutional report through the canonical kernel.

        The coordinator does NOT reimplement ingress, evidence resolution,
        or provenance. It delegates entirely to FederationKernel.

        All state is persisted through the canonical path.
        """
        return self.kernel.ingest_report(
            raw_payload,
            relevance_signals=relevance_signals,
            now=now,
            triggering_provenance_ids=triggering_provenance_ids,
        )

    def current_kernel_state(self) -> dict[str, Any]:
        """Query the current state of the canonical kernel."""
        return {
            "policy_version": self._policy_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            # (Further state queries will be added as F9 phases integrate)
        }

    # -------- Phase E: Outcome Evaluation + Bounded Learning --------

    def record_outcome(self, outcome_eval) -> tuple[bool, str]:
        """Record a mission outcome (append-only, immutable).

        Evaluates mission achievement against success criteria.
        No retroactive policy mutation (bounded learning).

        Semantic idempotency: same mission + evidence + success_criteria +
        policy_version + objective returns the EXISTING outcome_id and logs
        an audit attempt, rather than creating a duplicate outcome version.
        """
        try:
            outcome_dict = outcome_eval.to_dict()
            outcome_id, created = self.store.record_outcome(outcome_dict)
            if created:
                return True, f"outcome recorded: {outcome_id}"
            return True, f"idempotent match: existing outcome {outcome_id} reused, audit-logged"
        except Exception as e:
            return False, f"persistence error: {e}"

    def get_outcome_audit_log(self, mission_id: str) -> list[dict[str, Any]]:
        """Get all audit-logged re-evaluation attempts for a mission."""
        return self.store.get_outcome_audit_log(mission_id)

    def get_mission_outcomes(self, mission_id: str) -> list[dict[str, Any]]:
        """Get all outcome records for a mission (newest first)."""
        return self.store.get_mission_outcomes(mission_id)

    # -------- Phase F: Retry / Timeout / Leases / Circuit Breakers --------

    def decide_retry_for_mission(self, delegation_id: str, failure_class: Optional[str]):
        """Deterministic retry decision based on lifecycle history + failure class."""
        from executive.reliability import decide_retry, DEFAULT_RETRY_POLICY

        history = self.store.get_mission_history(delegation_id)
        retry_count = sum(1 for e in history if e.get("retry_count") is not None) if history else 0
        return decide_retry(retry_count=retry_count, failure_class=failure_class, policy=DEFAULT_RETRY_POLICY)

    def check_lease_expired(self, delegation_id: str, ttl_seconds: float, now: Optional[datetime] = None) -> bool:
        """Check whether the current lease on a mission has expired (restart-safe)."""
        from executive.reliability import is_lease_expired

        history = self.store.get_mission_history(delegation_id)
        if not history:
            return False
        latest = history[0]
        if not latest.get("lease_id"):
            return False
        return is_lease_expired(latest["timestamp"], ttl_seconds, now=now)

    def check_mission_timeout(self, delegation_id: str, timeout_seconds: float, now: Optional[datetime] = None) -> bool:
        """Check whether a RUNNING mission has exceeded its timeout."""
        from executive.reliability import is_mission_timed_out

        history = self.store.get_mission_history(delegation_id)
        running_events = [e for e in history if e.get("new_state") == "RUNNING"]
        if not running_events:
            return False
        return is_mission_timed_out(running_events[0]["timestamp"], timeout_seconds, now=now)

    def advance_circuit_breaker(
        self,
        institution_id: str,
        consecutive_failures: int,
        consecutive_successes: int,
        opened_at_iso: Optional[str] = None,
    ) -> tuple[str, str]:
        """Advance an institution's circuit breaker state deterministically."""
        from executive.reliability import next_circuit_state, DEFAULT_CIRCUIT_POLICY

        capacity = self.get_institution_capacity(institution_id) or {}
        current_state = capacity.get("circuit_state", "CLOSED")

        new_state, reason = next_circuit_state(
            current_state=current_state,
            consecutive_failures=consecutive_failures,
            consecutive_successes=consecutive_successes,
            opened_at_iso=opened_at_iso,
            policy=DEFAULT_CIRCUIT_POLICY,
        )

        capacity["circuit_state"] = new_state.value
        self.update_institution_capacity(institution_id, capacity)
        return new_state.value, reason

    # -------- Phase G: Policy Versioning + Escalation Governance --------

    def create_policy_version(self, policy_version) -> tuple[bool, str]:
        """Persist a new policy version. Status starts as given (typically DRAFT).

        Creating a version is NOT activating it -- AUTOMATIC_POLICY_MUTATION
        is prohibited; activation is a separate explicit call.
        """
        try:
            self.store.record_policy_version(policy_version.to_dict())
            return True, f"policy version recorded: {policy_version.policy_version_id}"
        except Exception as e:
            return False, f"persistence error: {e}"

    def activate_policy_version(
        self, policy_version_id: str, policy_id: str, effective_from: Optional[str] = None
    ) -> tuple[bool, str]:
        """Explicitly activate a policy version.

        Any currently ACTIVE version for the same policy_id is transitioned
        to SUPERSEDED (not deleted -- history is preserved for historical
        attribution). This is an EXPLICIT call, never triggered automatically
        by an observation or proposal.
        """
        effective_from = effective_from or datetime.now(timezone.utc).isoformat()

        current_active = self.store.get_active_policy_version(policy_id)
        if current_active:
            self.store.update_policy_version_status(
                current_active["policy_version_id"], "SUPERSEDED", effective_until=effective_from
            )

        self.store.update_policy_version_status(policy_version_id, "ACTIVE")
        return True, f"activated {policy_version_id}, superseded {current_active['policy_version_id'] if current_active else 'none'}"

    def rollback_policy_version(self, policy_id: str, rollback_target_id: str, reason: str) -> tuple[bool, str]:
        """Roll back to a prior policy version.

        The currently ACTIVE version is marked ROLLED_BACK (history preserved,
        never erased). The target version is reactivated as ACTIVE.
        """
        current_active = self.store.get_active_policy_version(policy_id)
        if current_active:
            self.store.update_policy_version_status(
                current_active["policy_version_id"], "ROLLED_BACK",
                effective_until=datetime.now(timezone.utc).isoformat(),
            )

        target = self.store.get_policy_version(rollback_target_id)
        if not target:
            return False, f"rollback target {rollback_target_id} not found"

        self.store.update_policy_version_status(rollback_target_id, "ACTIVE")
        return True, f"rolled back {policy_id} to {rollback_target_id}: {reason}"

    def resolve_active_policy(self, policy_id: str, at_timestamp: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Resolve the policy version active at a timestamp (default: now).

        Historical decisions must always resolve to the version that was
        ACTUALLY active at their own timestamp, never the current version.
        """
        return self.store.get_active_policy_version(policy_id, at_timestamp=at_timestamp)

    def get_policy_version_history(self, policy_id: str) -> list[dict[str, Any]]:
        """Full version history for a policy_id, newest first."""
        return self.store.get_policy_version_history(policy_id)

    def create_escalation(self, escalation) -> tuple[bool, str, str]:
        """Create an escalation, deduplicating against existing open ones.

        Returns (created, escalation_id, reason). If a semantically
        equivalent OPEN/ACKNOWLEDGED escalation already exists (same class +
        mission + trigger), that existing escalation_id is returned instead
        of creating a duplicate -- escalations must not flood the system.
        """
        escalation_dict = escalation.to_dict()
        dedup_key = escalation_dict["dedup_key"]

        existing = self.store.find_open_escalation_by_dedup_key(dedup_key)
        if existing:
            return False, existing["escalation_id"], "deduplicated: equivalent open escalation already exists"

        self.store.record_escalation(escalation_dict)
        return True, escalation.escalation_id, "escalation created"

    def resolve_escalation(
        self, escalation_id: str, status: str, resolution: dict[str, Any], resolver: str
    ) -> tuple[bool, str]:
        """Resolve/close an escalation."""
        try:
            self.store.resolve_escalation(escalation_id, status, resolution, resolver)
            return True, f"escalation {escalation_id} resolved as {status}"
        except Exception as e:
            return False, f"persistence error: {e}"

    def get_escalation(self, escalation_id: str) -> Optional[dict[str, Any]]:
        """Get a single escalation."""
        return self.store.get_escalation(escalation_id)

    def list_escalations(self, status: Optional[str] = None) -> list[dict[str, Any]]:
        """List escalations, optionally filtered by status."""
        return self.store.list_escalations(status=status)

    def expire_escalation(self, escalation_id: str, reason: str) -> tuple[bool, str]:
        """Expire an open escalation. Expired escalations must never later
        auto-execute; a new action requires fresh re-evaluation."""
        try:
            self.store.resolve_escalation(
                escalation_id, "EXPIRED", {"reason": reason}, "nexus_kernel"
            )
            return True, f"escalation {escalation_id} expired"
        except Exception as e:
            return False, f"persistence error: {e}"

    def evaluate_authority_gate(
        self, requested_action: str, requested_authority: str, current_ceiling: str
    ) -> tuple[bool, Optional[str], str]:
        """Evaluate an authority-gated action request.

        Never executes the action. Returns (allowed, escalation_class, reason).
        PERMANENTLY_PROHIBITED_ACTIONS (financial execution, publication,
        external communication) are always rejected regardless of authority
        level or any escalation outcome.
        """
        from executive.governance import evaluate_authority_request

        allowed, escalation_class, reason = evaluate_authority_request(
            requested_action, requested_authority, current_ceiling
        )
        return allowed, escalation_class.value if escalation_class else None, reason

    # -------- Phase H: Executive Memory + Provenance-Linked Recall --------

    def create_episode(self, episode) -> tuple[bool, str]:
        """Persist an episode index. This is an INDEX over canonical
        records, not a replacement source of truth."""
        try:
            self.store.record_episode(episode.to_dict())
            return True, f"episode recorded: {episode.episode_id}"
        except Exception as e:
            return False, f"persistence error: {e}"

    def update_episode(self, episode_id: str, **fields) -> None:
        """Update mutable episode fields as an episode progresses."""
        self.store.update_episode(episode_id, **fields)

    def recall_episode(self, episode_id: str) -> Optional[dict[str, Any]]:
        """Recall a single episode by id."""
        return self.store.get_episode(episode_id)

    def recall_by_trigger(self, root_trigger_id: str) -> list[dict[str, Any]]:
        """Recall all episodes rooted at a given trigger."""
        return self.store.find_episodes_by_trigger(root_trigger_id)

    def recall_by_mission(self, mission_id: str) -> list[dict[str, Any]]:
        """Recall all episodes involving a given mission."""
        return self.store.find_episodes_by_mission(mission_id)

    def recall_by_institution(self, institution_id: str) -> list[dict[str, Any]]:
        """Recall all episodes involving a given institution."""
        return self.store.find_episodes_by_institution(institution_id)

    def recall_by_outcome(self, outcome_id: str) -> list[dict[str, Any]]:
        """Recall all episodes linked to a given outcome."""
        return self.store.find_episodes_by_outcome(outcome_id)

    def record_semantic_memory(self, item) -> tuple[str, bool, str]:
        """Record a semantic memory item, subject to explicit promotion
        criteria and idempotency (same claim_class+statement+evidence basis
        while ACTIVE => existing semantic_id returned, no duplicate).
        """
        from executive.memory import is_eligible_for_semantic_promotion

        eligible, reason = is_eligible_for_semantic_promotion(item.claim_class)
        if not eligible:
            return "", False, reason

        semantic_id, created = self.store.record_semantic_memory(item.to_dict())
        return semantic_id, created, ("created" if created else "idempotent match: existing item reused")

    def recall_semantic_fact(self, semantic_id: str) -> Optional[dict[str, Any]]:
        """Recall a single semantic memory item."""
        return self.store.get_semantic_memory(semantic_id)

    def recall_semantic_by_claim_class(self, claim_class: str, status: Optional[str] = None) -> list[dict[str, Any]]:
        """Recall semantic memory items by claim_class, optionally filtered by status."""
        return self.store.find_semantic_by_claim_class(claim_class, status=status)

    def contradict_semantic_memory(self, semantic_id: str, conflicting_evidence_refs: list[str], reason: str) -> tuple[bool, str]:
        """Mark a semantic memory item CONTRADICTED. Never overwrites
        silently -- the conflicting evidence is what triggers this, and the
        original statement/evidence remain in the row, unaltered."""
        try:
            self.store.update_semantic_status(semantic_id, "CONTRADICTED")
            return True, f"marked CONTRADICTED: {reason}"
        except Exception as e:
            return False, f"persistence error: {e}"

    def invalidate_semantic_memory(self, semantic_id: str, reason: str) -> tuple[bool, str]:
        """Mark a semantic memory item INVALIDATED (supporting evidence broke down)."""
        try:
            self.store.update_semantic_status(
                semantic_id, "INVALIDATED", valid_until=datetime.now(timezone.utc).isoformat()
            )
            return True, f"invalidated: {reason}"
        except Exception as e:
            return False, f"persistence error: {e}"

    def mark_semantic_stale(self, semantic_id: str, reason: str) -> tuple[bool, str]:
        """Mark a semantic memory item STALE (freshness window expired).
        Still recallable as historical context, but never surfaced as
        current executive truth."""
        try:
            self.store.update_semantic_status(semantic_id, "STALE")
            return True, f"marked STALE: {reason}"
        except Exception as e:
            return False, f"persistence error: {e}"

    def recall_policy_context(self, policy_id: str, at_timestamp: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Procedural memory recall: the policy version in force at a
        timestamp (default now). Procedural memory IS the Phase G
        executive_policy_version registry -- no duplicate mutable store."""
        return self.store.get_active_policy_version(policy_id, at_timestamp=at_timestamp)

    def check_provenance_integrity(self, evidence_ref: str, expected_hash: Optional[str] = None) -> str:
        """Check whether an evidence reference's provenance chain is intact.

        Returns one of: OK, SOURCE_MISSING, EVIDENCE_DRIFT, PROVENANCE_BROKEN.
        Fails closed: absence of a resolvable baseline is SOURCE_MISSING, a
        hash mismatch is EVIDENCE_DRIFT -- never silently treated as verified.
        """
        try:
            with self.store.connection() as conn:
                row = conn.execute(
                    "SELECT sha256 FROM evidence_baseline WHERE ref = ? LIMIT 1",
                    (evidence_ref,),
                ).fetchone()
        except Exception:
            return "PROVENANCE_BROKEN"

        if not row:
            return "SOURCE_MISSING"

        if expected_hash is not None and row[0] != expected_hash:
            return "EVIDENCE_DRIFT"

        return "OK"

    def reconstruct_why_how(self, delegation_id: str) -> dict[str, Any]:
        """Mandatory WHY/HOW reconstruction, from persistence alone.

        Given a mission/delegation id, reconstructs:
          - lifecycle history (WHAT happened, in order)
          - policy version(s) referenced by lifecycle events (WHICH policy applied)
          - outcome(s) and their success-criteria basis (WHY classified that way)
          - learning observations derived from this mission (WHAT was learned)
          - escalations tied to this mission (WHAT remains unresolved)
          - dependencies (WHY this mission depended on/blocked others)
        """
        lifecycle_history = self.store.get_mission_history(delegation_id)
        outcomes = self.store.get_mission_outcomes(delegation_id)
        learning_events = self.store.get_learning_events(delegation_id)
        dependencies = self.store.get_mission_dependencies(delegation_id)
        prerequisites = self.store.get_mission_prerequisites(delegation_id)
        mission_escalations = [
            e for e in self.store.list_escalations() if e.get("mission_id") == delegation_id
        ]
        related_episodes = self.store.find_episodes_by_mission(delegation_id)

        return {
            "delegation_id": delegation_id,
            "lifecycle_history": lifecycle_history,
            "current_state": lifecycle_history[0]["new_state"] if lifecycle_history else None,
            "outcomes": outcomes,
            "learning_events": learning_events,
            "dependencies": dependencies,
            "prerequisites": prerequisites,
            "escalations": mission_escalations,
            "related_episodes": related_episodes,
        }

    # -------- Phase I: Autonomous Event-Driven Operating Loop --------

    def ingest_event(self, event) -> tuple[str, bool, str]:
        """Persist an event into the canonical inbox with idempotency.

        Returns (event_id_to_use, is_new, reason). Duplicate event_id replay
        AND duplicate semantic dedup_key both resolve to the SAME existing
        event_id -- no duplicate semantic mission is ever produced from a
        replayed or resubmitted event.
        """
        event_dict = event.to_dict()
        event_id, is_new = self.store.record_event(event_dict)
        if is_new:
            self.store.increment_counter("events_received")
            return event_id, True, "event recorded"
        self.store.increment_counter("events_deduplicated")
        return event_id, False, "duplicate event: existing envelope reused, no new mission will be created"

    def get_event(self, event_id: str) -> Optional[dict[str, Any]]:
        return self.store.get_event(event_id)

    def process_event_to_mission(
        self,
        event_id: str,
        attention_accept: bool,
        attention_reason: str,
        priority_decision=None,
    ) -> tuple[Optional[str], str]:
        """Advance a RECEIVED event through attention -> priority -> canonical
        mission creation. The mission identity IS the canonical delegation_id
        (== event_id in this direct-trigger path) -- no autonomous_loop_mission
        side object is created.

        Returns (delegation_id_or_None, reason). A rejected/low-attention
        event legitimately produces no mission -- this is NOT a failure.
        """
        event = self.store.get_event(event_id)
        if event is None:
            return None, "event not found"

        if event["status"] not in ("RECEIVED", "VALIDATED"):
            return None, f"event not eligible for processing: status={event['status']}"

        self.store.update_event_status(event_id, "VALIDATED")

        if not attention_accept:
            self.store.update_event_status(event_id, "PROCESSED")
            self.store.increment_counter("events_rejected")
            return None, f"NO_ACTION_REQUIRED: {attention_reason}"

        delegation_id = event_id  # canonical identity: event IS the mission trigger
        self.store.update_event_status(event_id, "PROCESSING", resulting_delegation_id=delegation_id)

        reason = f"attention accepted: {attention_reason}"
        if priority_decision is not None:
            reason += f"; priority={priority_decision.priority_class.value}"

        success, transition_reason = self.transition_mission(delegation_id, MissionState.PROPOSED, reason)
        if not success:
            return None, transition_reason

        self.store.increment_counter("missions_created")
        return delegation_id, "mission created from event"

    def advance_to_queued(
        self,
        delegation_id: str,
        dependency_reason: str = "dependencies satisfied",
        capacity_reason: str = "capacity admissible",
    ) -> tuple[bool, str]:
        """Advance a PROPOSED mission through dependency + capacity gates to
        QUEUED, where it becomes eligible for atomic lease claim. Uses the
        real Phase B state machine and Phase C/D gate checks -- no bypass."""
        success, reason = self.transition_mission(delegation_id, MissionState.VALIDATED, dependency_reason)
        if not success:
            return False, reason
        success, reason = self.transition_mission(delegation_id, MissionState.QUEUED, capacity_reason)
        return success, reason

    def claim_mission_atomic(
        self, delegation_id: str, lease_id: str, actor: str, reason: str,
        institution_id: Optional[str] = None,
    ) -> tuple[bool, str]:
        """Atomically claim a mission lease -- safe across concurrent OS
        processes (see FederationStore.atomic_claim_mission). Exactly one
        caller wins; the loser observes the canonical lease, never executes
        duplicate work.

        F10C.1: pass `institution_id` to enforce capacity as part of the
        SAME atomic claim (structural, not advisory) -- a claim attempt
        against an institution already at max_concurrent_missions fails
        here, inside the lock, rather than relying on a separate
        is_institution_admissible() check the caller might forget."""
        won, claim_reason = self.store.atomic_claim_mission(
            delegation_id, lease_id, actor, reason, policy_version=self._policy_version,
            institution_id=institution_id,
        )
        if won:
            self.store.increment_counter("missions_claimed")
        return won, claim_reason

    def ingest_specialist_result(
        self,
        delegation_id: str,
        result_evidence_refs: list[str],
        result_provenance_refs: list[str],
        claimed_success: bool,
    ) -> tuple[bool, str]:
        """Result ingestion through canonical evidence linkage -- the
        coordinator does NOT trust a raw Python return value as SUCCESS.
        The evidence/provenance refs are what outcome evaluation actually
        checks; claimed_success alone is not sufficient (see
        evaluate_outcome_from_evidence)."""
        current_state = self.get_mission_state(delegation_id)
        if current_state == "CLAIMED":
            success, reason = self.transition_mission(delegation_id, MissionState.RUNNING, "specialist dispatched")
            if not success:
                return False, reason
        elif current_state != "RUNNING":
            return False, f"mission not in a dispatchable state: {current_state}"

        completion_state = MissionState.COMPLETED if claimed_success else MissionState.FAILED
        success, reason = self.transition_mission(
            delegation_id,
            completion_state,
            f"specialist result ingested: claimed_success={claimed_success}, "
            f"evidence_refs={result_evidence_refs}",
            evidence_refs=result_evidence_refs,
        )
        return success, reason

    def evaluate_outcome_from_evidence(
        self,
        delegation_id: str,
        objective: str,
        success_criteria: list[str],
        evidence_refs: list[str],
        claimed_success: bool,
    ):
        """Outcome evaluation that does NOT equate exit-code-zero with
        SUCCESS. If claimed_success is True but no evidence_refs support it,
        the outcome is INSUFFICIENT_EVIDENCE, not SUCCESS."""
        from executive.outcome import OutcomeEvaluation, OutcomeClass
        import uuid

        if claimed_success and not evidence_refs:
            outcome_class = OutcomeClass.INSUFFICIENT_EVIDENCE
            criteria_met: list[str] = []
        elif claimed_success and evidence_refs:
            outcome_class = OutcomeClass.SUCCESS
            criteria_met = list(success_criteria)
        else:
            outcome_class = OutcomeClass.FAILED
            criteria_met = []

        outcome = OutcomeEvaluation(
            outcome_id=str(uuid.uuid4()),
            mission_id=delegation_id,
            delegation_id=delegation_id,
            outcome_class=outcome_class,
            evaluated_at=datetime.now(timezone.utc),
            objective=objective,
            success_criteria=success_criteria,
            criteria_met=criteria_met,
            criteria_unmet=[c for c in success_criteria if c not in criteria_met],
            evidence_refs=evidence_refs,
        )
        success, reason = self.record_outcome(outcome)
        if success:
            self.store.increment_counter("outcomes_recorded")
        return outcome, success, reason

    def get_loop_counters(self) -> dict[str, int]:
        """Loop observability -- measured counters only, no vanity scores."""
        return self.store.get_all_counters()
