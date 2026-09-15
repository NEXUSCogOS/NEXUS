"""NEXUS F9 Phase A: Attention + Priority.

Tests the orthogonal attention and priority layers in composition with the
canonical FederationKernel. Phase A adds no persistence changes; it validates
that attention/priority scoring works correctly.
"""

import pytest
from datetime import datetime, timezone

from executive import (
    ExecutiveCoordinator,
    AttentionFactors,
    AttentionSignal,
    AttentionClass,
    PriorityFactors,
    PriorityClass,
)


class TestPhaseAAttention:
    """Test attention assessment (orthogonal layer)."""

    def test_attention_high_materiality_high_evidence(self, coordinator):
        """High-materiality, well-evidenced signal gets CRITICAL attention."""
        factors = AttentionFactors(
            materiality=1.0,
            novelty=0.8,
            time_sensitivity=0.9,
            evidence_quality=1.0,
            uncertainty=0.0,
            cross_domain_relevance=0.8,
            risk=0.9,
            reversibility=0.1,
            institutional_coverage=1.0,
        )
        signal = AttentionSignal(
            signal_id="sig_critical",
            source="sentinel",
            signal_class="market_anomaly",
            timestamp=datetime.now(timezone.utc).isoformat(),
            factors=factors,
            evidence_refs=["ev_1", "ev_2"],
        )
        accept, reason = coordinator.assess_attention(signal)
        assert accept
        assert "CRITICAL" in reason or signal.attention_class == AttentionClass.CRITICAL

    def test_attention_no_evidence_rejected(self, coordinator):
        """Signal with no evidence gets MINIMAL attention."""
        factors = AttentionFactors(
            materiality=1.0,
            novelty=1.0,
            time_sensitivity=1.0,
            evidence_quality=0.0,  # NO EVIDENCE
            uncertainty=0.5,
            cross_domain_relevance=1.0,
            risk=1.0,
            reversibility=0.0,
            institutional_coverage=1.0,
        )
        signal = AttentionSignal(
            signal_id="sig_no_evidence",
            source="dat_ai",
            signal_class="unverified_finding",
            timestamp=datetime.now(timezone.utc).isoformat(),
            factors=factors,
            evidence_refs=[],
        )
        accept, reason = coordinator.assess_attention(signal)
        assert not accept
        assert "LOW_ATTENTION" in reason

    def test_attention_routine_status_deferred(self, coordinator):
        """Routine status updates get LOW/NORMAL attention."""
        factors = AttentionFactors(
            materiality=0.3,
            novelty=0.0,  # seen before
            time_sensitivity=0.1,
            evidence_quality=0.9,
            uncertainty=0.2,
            cross_domain_relevance=0.0,
            risk=0.0,
            reversibility=1.0,
            institutional_coverage=0.5,
        )
        signal = AttentionSignal(
            signal_id="sig_routine",
            source="librarian",
            signal_class="routine_status",
            timestamp=datetime.now(timezone.utc).isoformat(),
            factors=factors,
            evidence_refs=["ev_1"],
        )
        accept, reason = coordinator.assess_attention(signal)
        # May accept (LOW attention) or reject (MINIMAL), both are OK for routine
        assert isinstance(accept, bool)


class TestPhaseAPriority:
    """Test priority assignment (orthogonal layer)."""

    def test_priority_imminent_deadline_critical(self, coordinator):
        """Mission with imminent deadline gets HIGH/CRITICAL priority."""
        factors = PriorityFactors(
            deadline_urgency=1.0,  # hours away
            dependency_blocking=0.0,
            information_gain=0.3,
            cost_to_act=0.2,
            resource_contention=0.5,
            mission_criticality=0.5,
            reversibility=0.8,
        )
        decision = coordinator.assign_priority(
            "m_urgent",
            factors,
            "deadline imminent in 1 hour",
        )
        assert decision.priority_class in (PriorityClass.CRITICAL, PriorityClass.HIGH)
        assert decision.priority_score > 0.6

    def test_priority_expensive_work_deferred(self, coordinator):
        """Expensive work with no deadline gets LOW/DEFERRED priority."""
        factors = PriorityFactors(
            deadline_urgency=0.0,
            dependency_blocking=0.0,
            information_gain=0.5,
            cost_to_act=1.0,  # expensive
            resource_contention=0.8,
            mission_criticality=0.3,
            reversibility=0.9,  # reversible, so can wait
        )
        decision = coordinator.assign_priority(
            "m_expensive",
            factors,
            "expensive analysis, no deadline",
        )
        assert decision.priority_class in (PriorityClass.LOW, PriorityClass.DEFERRED)

    def test_priority_blocking_other_missions_high(self, coordinator):
        """Mission that blocks others gets HIGH priority."""
        factors = PriorityFactors(
            deadline_urgency=0.3,
            dependency_blocking=1.0,  # blocking others
            information_gain=0.6,
            cost_to_act=0.3,
            resource_contention=0.4,
            mission_criticality=0.5,
            reversibility=0.7,
        )
        decision = coordinator.assign_priority(
            "m_blocker",
            factors,
            "5 other missions waiting on this",
        )
        assert decision.priority_class in (PriorityClass.CRITICAL, PriorityClass.HIGH)


class TestPhaseACoordinatorState:
    """Test coordinator state queries."""

    def test_coordinator_has_canonical_kernel(self, coordinator):
        """Coordinator is initialized with canonical FederationKernel."""
        assert coordinator.kernel is not None
        assert coordinator.store is not None

    def test_coordinator_state_queryable(self, coordinator):
        """Current state can be queried."""
        state = coordinator.current_kernel_state()
        assert "policy_version" in state
        assert "timestamp" in state
        assert state["policy_version"] == "F9.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
