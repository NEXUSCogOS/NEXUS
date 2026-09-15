"""Test suite for AuthorityGate governance layer.

Tests verify approval/denial logic, risk classification, audit trail creation,
and edge cases for the autonomous repair authorization system.
"""

import pytest
from systems.engineering_studio.studio_v3.governance.authority_gate import AuthorityGate


class TestAuthorityGateApproval:
    """Test authorization approval logic."""

    def test_approve_low_risk_auto_approved_task(self):
        """Verify approval for LOW-risk, pre-approved tasks."""
        gate = AuthorityGate()
        task = {
            'task_id': 'readme_abc123',
            'type': 'missing_readme',
            'risk_level': 'LOW',
            'auto_approve': True,
        }
        assert gate.approve(task) is True

    def test_reject_high_risk_task(self):
        """Verify rejection of HIGH-risk tasks."""
        gate = AuthorityGate()
        task = {
            'task_id': 'delete_abc123',
            'type': 'missing_readme',
            'risk_level': 'HIGH',
            'auto_approve': True,
        }
        assert gate.approve(task) is False

    def test_reject_task_without_auto_approve_flag(self):
        """Verify rejection when auto_approve flag is False."""
        gate = AuthorityGate()
        task = {
            'task_id': 'readme_abc123',
            'type': 'missing_readme',
            'risk_level': 'LOW',
            'auto_approve': False,
        }
        assert gate.approve(task) is False

    def test_reject_unknown_task_type(self):
        """Verify rejection of unapproved task types."""
        gate = AuthorityGate()
        task = {
            'task_id': 'custom_abc123',
            'type': 'custom_action',
            'risk_level': 'LOW',
            'auto_approve': True,
        }
        assert gate.approve(task) is False

    def test_approve_only_missing_readme_type(self):
        """Verify only 'missing_readme' is in approved types."""
        gate = AuthorityGate()

        # Should approve missing_readme
        task_readme = {
            'task_id': 'readme_abc123',
            'type': 'missing_readme',
            'risk_level': 'LOW',
            'auto_approve': True,
        }
        assert gate.approve(task_readme) is True

        # Should reject other types
        task_license = {
            'task_id': 'license_abc123',
            'type': 'missing_license',
            'risk_level': 'LOW',
            'auto_approve': True,
        }
        assert gate.approve(task_license) is False

    def test_reject_missing_risk_level(self):
        """Verify rejection when risk_level is missing."""
        gate = AuthorityGate()
        task = {
            'task_id': 'readme_abc123',
            'type': 'missing_readme',
            'auto_approve': True,
        }
        assert gate.approve(task) is False

    def test_reject_missing_auto_approve_flag(self):
        """Verify rejection when auto_approve flag is missing."""
        gate = AuthorityGate()
        task = {
            'task_id': 'readme_abc123',
            'type': 'missing_readme',
            'risk_level': 'LOW',
        }
        assert gate.approve(task) is False


class TestAuthorityGateAuditTrail:
    """Test audit trail creation."""

    def test_create_approved_audit_entry(self):
        """Verify audit entry for approved decisions."""
        gate = AuthorityGate()
        task = {
            'task_id': 'readme_abc123',
            'type': 'missing_readme',
            'risk_level': 'LOW',
        }

        entry = gate.create_audit_entry(task, approved=True, reason='Pre-approved pattern')

        assert entry['task_id'] == 'readme_abc123'
        assert entry['decision'] == 'approved'
        assert entry['reason'] == 'Pre-approved pattern'
        assert entry['risk_level'] == 'LOW'
        assert entry['task_type'] == 'missing_readme'

    def test_create_rejected_audit_entry(self):
        """Verify audit entry for rejected decisions."""
        gate = AuthorityGate()
        task = {
            'task_id': 'custom_abc123',
            'type': 'custom_action',
            'risk_level': 'MEDIUM',
        }

        entry = gate.create_audit_entry(task, approved=False, reason='High risk, requires human review')

        assert entry['task_id'] == 'custom_abc123'
        assert entry['decision'] == 'rejected'
        assert entry['reason'] == 'High risk, requires human review'
        assert entry['risk_level'] == 'MEDIUM'
        assert entry['task_type'] == 'custom_action'

    def test_audit_entry_without_reason(self):
        """Verify audit entry with empty reason."""
        gate = AuthorityGate()
        task = {
            'task_id': 'readme_xyz789',
            'type': 'missing_readme',
            'risk_level': 'LOW',
        }

        entry = gate.create_audit_entry(task, approved=True)

        assert entry['decision'] == 'approved'
        assert entry['reason'] == ''

    def test_audit_entry_missing_task_id(self):
        """Verify audit entry when task_id is missing."""
        gate = AuthorityGate()
        task = {
            'type': 'missing_readme',
            'risk_level': 'LOW',
        }

        entry = gate.create_audit_entry(task, approved=True)

        assert entry['task_id'] is None
        assert entry['decision'] == 'approved'

    def test_audit_entry_missing_risk_level(self):
        """Verify audit entry when risk_level is missing."""
        gate = AuthorityGate()
        task = {
            'task_id': 'readme_abc123',
            'type': 'missing_readme',
        }

        entry = gate.create_audit_entry(task, approved=True)

        assert entry['task_id'] == 'readme_abc123'
        assert entry['risk_level'] is None


class TestAuthorityGateEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_approve_with_extra_fields(self):
        """Verify approval works with extra fields in task dict."""
        gate = AuthorityGate()
        task = {
            'task_id': 'readme_abc123',
            'type': 'missing_readme',
            'risk_level': 'LOW',
            'auto_approve': True,
            'extra_field': 'should_be_ignored',
            'priority': 'high',
        }
        assert gate.approve(task) is True

    def test_case_sensitive_risk_level(self):
        """Verify that risk level check is case-sensitive (must be 'LOW', not 'low')."""
        gate = AuthorityGate()
        task_lowercase = {
            'task_id': 'readme_abc123',
            'type': 'missing_readme',
            'risk_level': 'low',  # lowercase
            'auto_approve': True,
        }
        assert gate.approve(task_lowercase) is False

    def test_case_sensitive_task_type(self):
        """Verify that task type check is case-sensitive."""
        gate = AuthorityGate()
        task_uppercase = {
            'task_id': 'readme_abc123',
            'type': 'MISSING_README',  # uppercase
            'risk_level': 'LOW',
            'auto_approve': True,
        }
        assert gate.approve(task_uppercase) is False

    def test_approve_with_none_auto_approve_value(self):
        """Verify rejection when auto_approve is None."""
        gate = AuthorityGate()
        task = {
            'task_id': 'readme_abc123',
            'type': 'missing_readme',
            'risk_level': 'LOW',
            'auto_approve': None,
        }
        assert gate.approve(task) is False

    def test_approve_empty_task_dict(self):
        """Verify rejection of empty task dict."""
        gate = AuthorityGate()
        task = {}
        assert gate.approve(task) is False

    def test_audit_entry_preserves_all_task_fields(self):
        """Verify audit entry captures all relevant task metadata."""
        gate = AuthorityGate()
        task = {
            'task_id': 'readme_abc123',
            'type': 'missing_readme',
            'risk_level': 'LOW',
            'priority': 'high',
            'assigned_to': 'system',
        }

        entry = gate.create_audit_entry(task, approved=True, reason='Auto-approved')

        # Only task-related fields should be in audit entry
        assert 'priority' not in entry
        assert 'assigned_to' not in entry
        # Required fields should be present
        assert entry['task_id'] == 'readme_abc123'
        assert entry['task_type'] == 'missing_readme'
        assert entry['risk_level'] == 'LOW'
