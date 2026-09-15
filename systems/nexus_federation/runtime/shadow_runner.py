"""F10B: Real-Runtime Shadow Federation Runner.

SHADOW / OBSERVE_ONLY. This runner does NOT own production scheduling, does
NOT control any specialist, and structurally CANNOT dispatch an external
action -- ExecutiveCoordinator.evaluate_authority_gate is consulted for every
recommendation and `would_dispatch` is hardcoded False for the whole runtime
mode, not merely documented.

Composes the EXISTING F9 architecture (ExecutiveCoordinator -> FederationKernel
-> FederationStore) exactly as built in F9 Phases A-I. Creates NO new kernel,
store, mission authority, or scheduler. Adapters here only translate each
specialist's EXISTING stable output/interface into a generic InstitutionalReport
or ExecutiveEvent -- no specialist internals are modified.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

FEDERATION_ROOT = Path(__file__).resolve().parents[1]
NEXUS_SYSTEMS_ROOT = FEDERATION_ROOT.parent
sys.path.insert(0, str(FEDERATION_ROOT))
sys.path.insert(0, str(NEXUS_SYSTEMS_ROOT))
sys.path.insert(0, str(NEXUS_SYSTEMS_ROOT / "dat_ai"))
sys.path.insert(0, str(NEXUS_SYSTEMS_ROOT / "librarian"))
sys.path.insert(0, str(NEXUS_SYSTEMS_ROOT / "news_intelligence"))

from ingress.contract_registry import bootstrap_federation_registry, register_contract
from contracts.generic import validate_report as validate_generic_report
from kernel import FederationKernel
from persistence.db import FederationStore
from executive.coordinator import ExecutiveCoordinator
from executive.attention import AttentionFactors, AttentionSignal
from executive.priority import PriorityFactors


RUNTIME_MODE = "OBSERVE_ONLY"


class ShadowAuthorityViolation(RuntimeError):
    """Raised if any code path attempts an external action while in
    OBSERVE_ONLY mode. This is a structural fail-closed guard, not a comment."""


def assert_observe_only() -> None:
    if RUNTIME_MODE != "OBSERVE_ONLY":
        raise ShadowAuthorityViolation(f"unexpected runtime mode: {RUNTIME_MODE}")


class ShadowRunner:
    """The one canonical shadow-mode entry point. Composes existing F9
    components; creates none of its own."""

    def __init__(self, store_path: str | Path):
        assert_observe_only()
        self.store = FederationStore(store_path)
        bootstrap_federation_registry()
        # Engineering Studio is not in the F9 default bootstrap set (F1-F9
        # never delegated to it); registering it here uses the SAME
        # register_contract() mechanism bootstrap_federation_registry()
        # itself uses -- not a new registry, not a contract mutation.
        register_contract("engineering_studio", validate_generic_report, frozenset({"1.0.0"}))
        self.kernel = FederationKernel(self.store)
        self.coordinator = ExecutiveCoordinator(self.store)

    # ---- structural dispatch guard -----------------------------------

    def evaluate_would_dispatch(
        self, requested_action: str, requested_authority: str, current_ceiling: str
    ) -> dict[str, Any]:
        """The ONLY path that decides whether an action would proceed.
        Always returns would_dispatch=False in this runtime mode -- this is
        enforced structurally (assert_observe_only), not left to caller
        discipline."""
        assert_observe_only()
        allowed, escalation_class, reason = self.coordinator.evaluate_authority_gate(
            requested_action, requested_authority, current_ceiling
        )
        return {
            "would_dispatch": False,  # hardcoded for OBSERVE_ONLY, independent of `allowed`
            "authority_would_have_allowed": allowed,
            "escalation_class": escalation_class,
            "blocked_reason": "OBSERVE_ONLY runtime mode -- no dispatch is ever performed" if allowed else reason,
        }

    # ---- ingestion + shadow decision -----------------------------------

    def ingest_and_decide(
        self,
        raw_payload: dict[str, Any],
        *,
        attention_factors: AttentionFactors,
        priority_factors: Optional[PriorityFactors] = None,
        recommended_action: str = "ANALYSE",
        recommended_recipient: Optional[str] = None,
        source_label: str = "",
    ) -> dict[str, Any]:
        """Ingest a real InstitutionalReport through the canonical kernel,
        run attention/priority, evaluate the authority gate for the
        recommended action, and persist a shadow decision episode. No
        dispatch occurs."""
        assert_observe_only()

        kernel_result = self.kernel.ingest_report(raw_payload)

        signal = AttentionSignal(
            signal_id=str(uuid.uuid4()),
            source=source_label or raw_payload.get("institution", "unknown"),
            signal_class="institutional_report",
            timestamp=datetime.now(timezone.utc).isoformat(),
            factors=attention_factors,
            evidence_refs=raw_payload.get("evidence_refs", []),
        )
        attention_accept, attention_reason = self.coordinator.assess_attention(signal)

        priority_decision = None
        if priority_factors is not None:
            priority_decision = self.coordinator.assign_priority(
                mission_id=f"shadow-{signal.signal_id}",
                factors=priority_factors,
                basis=f"shadow assessment for {source_label}",
            )

        dispatch_eval = self.evaluate_would_dispatch(
            recommended_action, "A1", "A3"  # ANALYSE-class actions default to A1 request, A3 ceiling
        )

        source_institution = raw_payload.get("institution", "unknown")
        evidence_refs = raw_payload.get("evidence_refs", [])
        proposed_id = str(uuid.uuid4())

        decision_record = {
            "shadow_decision_id": proposed_id,
            "source_institution": source_institution,
            "source_cycle_id": raw_payload.get("cycle_id"),
            "attention_class": signal.attention_class.value,
            "attention_score": signal.attention_score,
            "priority_class": priority_decision.priority_class.value if priority_decision else None,
            "priority_score": priority_decision.priority_score if priority_decision else None,
            "recommended_action": recommended_action,
            "recommended_recipient": recommended_recipient,
            "authority_required": "A1",
            "would_dispatch": dispatch_eval["would_dispatch"],
            "authority_would_have_allowed": dispatch_eval["authority_would_have_allowed"],
            "blocked_reason": dispatch_eval["blocked_reason"],
            "evidence_refs": evidence_refs,
            "policy_version": "F9.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        # Semantically idempotent: same institution+cycle_id+evidence basis
        # returns the EXISTING shadow_decision_id, never a duplicate row.
        shadow_decision_id, decision_created = self.store.record_shadow_decision(decision_record)

        episode = None
        try:
            from executive.memory import Episode, EpisodeType

            episode_obj = Episode(
                episode_id=f"shadow-episode-{shadow_decision_id}",
                episode_type=EpisodeType.INSTITUTIONAL_INGEST,
                root_trigger_id=shadow_decision_id,
                institution_ids=[source_institution],
                evidence_refs=evidence_refs,
                status="CLOSED",
            )
            self.coordinator.create_episode(episode_obj)
            episode = episode_obj.episode_id
        except Exception:
            pass  # episode creation is best-effort observability, not required for the shadow decision itself

        return {
            "shadow_decision_id": shadow_decision_id,
            "shadow_decision_created": decision_created,
            "kernel_accepted": kernel_result.accepted,
            "kernel_reason": kernel_result.reason,
            "temporal_classification": kernel_result.temporal_classification,
            "attention_accept": attention_accept,
            "attention_reason": attention_reason,
            "attention_class": signal.attention_class.value,
            "priority_class": priority_decision.priority_class.value if priority_decision else None,
            "priority_score": priority_decision.priority_score if priority_decision else None,
            "recommended_action": recommended_action,
            "recommended_recipient": recommended_recipient,
            "would_dispatch": dispatch_eval["would_dispatch"],
            "authority_would_have_allowed": dispatch_eval["authority_would_have_allowed"],
            "blocked_reason": dispatch_eval["blocked_reason"],
            "evidence_refs": evidence_refs,
            "policy_version": "F9.0",
            "episode_id": episode,
            "created_at": decision_record["created_at"],
        }
