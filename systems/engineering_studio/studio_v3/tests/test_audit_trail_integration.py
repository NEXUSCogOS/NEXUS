"""Tests for audit trail integration in AutonomousProjectExecutor"""
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import pytest
from systems.engineering_studio.studio_v3.core.semantic_core import SemanticKernel, OperationType, AuditLevel
from systems.engineering_studio.studio_v3.execution.autonomous_project_executor import AutonomousProjectExecutor


class TestAuditTrailIntegration:
    """Test semantic audit trail integration with project executor"""

    @pytest.fixture
    def executor(self):
        """Create executor with semantic kernel"""
        kernel = SemanticKernel(audit_level=AuditLevel.COMPLIANCE)
        executor = AutonomousProjectExecutor(semantic_kernel=kernel)
        return executor

    @pytest.fixture
    def sample_project(self):
        """Create a sample project"""
        return {
            "name": "TestProject",
            "requirements": "Build a test system",
            "domain": "testing",
        }

    def test_executor_has_semantic_kernel(self, executor):
        """Test executor is initialized with semantic kernel"""
        assert executor.semantic is not None
        assert executor.semantic.audit is not None

    def test_executor_has_audit_trail(self, executor):
        """Test executor maintains audit trail"""
        assert isinstance(executor.audit_trail, list)
        assert len(executor.audit_trail) == 0

    def test_record_decision(self, executor):
        """Test recording a decision"""
        decision = executor._record_decision(
            decision_type="architecture_design",
            hypothesis="Use MVC pattern for modularity",
            current_state={"modularity": 0.5},
            projected_outcome={"modularity": 0.9}
        )

        assert decision is not None
        assert decision.decision_type == "architecture_design"
        assert decision.hypothesis == "Use MVC pattern for modularity"
        assert len(executor.audit_trail) > 0

    def test_record_audit_entry(self, executor):
        """Test recording audit entries"""
        entity_id = uuid4()
        entry = executor._record_audit_entry(
            entity_id=entity_id,
            entity_type="Decision",
            operation=OperationType.CREATE,
            new_state={"status": "created"},
            reason="Test decision creation"
        )

        assert entry is not None
        assert entry.entity_id == entity_id
        assert entry.entity_type == "Decision"
        assert entry.operation == OperationType.CREATE
        assert len(executor.audit_trail) == 1

    def test_get_audit_history(self, executor):
        """Test retrieving audit history"""
        entity_id = uuid4()
        executor._record_audit_entry(
            entity_id=entity_id,
            entity_type="Decision",
            operation=OperationType.CREATE,
            reason="First audit"
        )
        executor._record_audit_entry(
            entity_id=entity_id,
            entity_type="Decision",
            operation=OperationType.UPDATE,
            reason="Second audit"
        )

        history = executor.get_audit_history()
        assert len(history) == 2
        assert history[0].reason == "First audit"
        assert history[1].reason == "Second audit"

    def test_get_decision_history(self, executor):
        """Test retrieving decision history"""
        decision1 = executor._record_decision(
            decision_type="type1",
            hypothesis="Hypothesis 1",
            current_state={"metric": 0.5},
            projected_outcome={"metric": 0.8}
        )

        decision2 = executor._record_decision(
            decision_type="type2",
            hypothesis="Hypothesis 2",
            current_state={"metric": 0.6},
            projected_outcome={"metric": 0.9}
        )

        decisions = executor.get_decision_history()
        assert len(decisions) == 2
        assert str(decision1.semantic_id) in decisions
        assert str(decision2.semantic_id) in decisions

    def test_execute_project_creates_audit_trail(self, executor, sample_project):
        """Test that executing project creates audit trail"""
        result = executor.execute_project(sample_project)

        assert result.audit_entries is not None
        assert len(result.audit_entries) > 0
        assert result.success is True

    def test_audit_entry_completeness(self, executor):
        """Test that audit entries contain all required information"""
        entity_id = uuid4()
        previous_state = {"step": 1}
        new_state = {"step": 2}
        reason = "Progressed to step 2"

        entry = executor._record_audit_entry(
            entity_id=entity_id,
            entity_type="StepProgression",
            operation=OperationType.UPDATE,
            previous_state=previous_state,
            new_state=new_state,
            reason=reason
        )

        assert entry.entity_id == entity_id
        assert entry.entity_type == "StepProgression"
        assert entry.operation == OperationType.UPDATE
        assert entry.previous_state == previous_state
        assert entry.new_state == new_state
        assert entry.reason == reason
        assert entry.timestamp is not None

    def test_audit_entry_immutability(self, executor):
        """Test that audit entries are immutable"""
        entity_id = uuid4()
        entry = executor._record_audit_entry(
            entity_id=entity_id,
            entity_type="Test",
            operation=OperationType.CREATE
        )

        # AuditEntry is frozen (immutable)
        with pytest.raises(Exception):  # FrozenInstanceError
            entry.reason = "modified"

    def test_semantic_transaction_context(self, executor):
        """Test semantic transaction context manager"""
        from systems.engineering_studio.studio_v3.core.semantic_core import semantic_transaction
        entity_id = uuid4()

        with semantic_transaction(
            executor.semantic.audit,
            entity_id,
            "TestEntity",
            OperationType.CREATE,
            reason="Test transaction"
        ):
            pass  # Simulate work

        history = executor.semantic.audit.get_history(entity_id)
        assert len(history) > 0
        assert history[0].entity_type == "TestEntity"

    def test_multiple_decisions_tracked(self, executor, sample_project):
        """Test that multiple decisions are tracked independently"""
        sample_project["requirements"] = "Build system A"
        result1 = executor.execute_project(sample_project)

        executor2 = AutonomousProjectExecutor(
            semantic_kernel=SemanticKernel(audit_level=AuditLevel.COMPLIANCE)
        )
        sample_project["requirements"] = "Build system B"
        result2 = executor2.execute_project(sample_project)

        # Each executor should have independent audit trails
        assert len(result1.audit_entries) > 0
        assert len(result2.audit_entries) > 0
        # Project IDs should be different
        assert executor.project_id != executor2.project_id

    def test_audit_compliance_level(self):
        """Test audit trail with COMPLIANCE level"""
        kernel = SemanticKernel(audit_level=AuditLevel.COMPLIANCE)
        executor = AutonomousProjectExecutor(semantic_kernel=kernel)

        entity_id = uuid4()
        executor._record_audit_entry(
            entity_id=entity_id,
            entity_type="ComplianceTest",
            operation=OperationType.CREATE
        )

        # Should be recorded
        assert len(executor.audit_trail) == 1

    def test_audit_silent_level(self):
        """Test audit trail with SILENT level"""
        kernel = SemanticKernel(audit_level=AuditLevel.SILENT)
        executor = AutonomousProjectExecutor(semantic_kernel=kernel)

        entity_id = uuid4()
        executor._record_audit_entry(
            entity_id=entity_id,
            entity_type="SilentTest",
            operation=OperationType.CREATE
        )

        # Executor local trail still records (for tracking purposes)
        # But semantic kernel's entries list should be empty (SILENT level)
        assert len(executor.audit_trail) > 0
        assert executor.semantic.audit.entries == []
