"""Test suite for cognition layer (Prioritiser and Planner).

Tests verify risk classification, task generation, decision logic,
and acceptance criteria for repair planning.
"""

import pytest
import uuid
from systems.engineering_studio.studio_v3.cognition.prioritiser import Prioritiser
from systems.engineering_studio.studio_v3.cognition.planner import Planner


class TestPrioritiserClassification:
    """Test finding classification and risk assessment."""

    def test_classify_missing_readme_finding(self):
        """Verify classification of missing_readme finding."""
        prioritiser = Prioritiser()
        finding = {
            'type': 'missing_readme',
            'path': '/repo',
            'severity': 'LOW',
        }

        classified = prioritiser.classify_finding(finding)

        assert classified['risk_level'] == 'LOW'
        assert classified['auto_approve'] is True
        assert classified['max_attempts'] == 3

    def test_classify_unknown_finding_type(self):
        """Verify unknown finding types get UNKNOWN risk level."""
        prioritiser = Prioritiser()
        finding = {
            'type': 'unknown_issue',
            'path': '/repo',
            'severity': 'MEDIUM',
        }

        classified = prioritiser.classify_finding(finding)

        assert classified['risk_level'] == 'UNKNOWN'
        assert classified['auto_approve'] is False
        assert classified['max_attempts'] == 0

    def test_classify_preserves_original_fields(self):
        """Verify classification preserves original finding fields."""
        prioritiser = Prioritiser()
        finding = {
            'type': 'missing_readme',
            'path': '/my/repo',
            'severity': 'LOW',
            'description': 'Missing documentation',
        }

        classified = prioritiser.classify_finding(finding)

        assert classified['path'] == '/my/repo'
        assert classified['severity'] == 'LOW'
        assert classified['description'] == 'Missing documentation'

    def test_classify_adds_new_fields(self):
        """Verify classification adds risk, approval, and retry fields."""
        prioritiser = Prioritiser()
        finding = {
            'type': 'missing_readme',
        }

        classified = prioritiser.classify_finding(finding)

        assert 'risk_level' in classified
        assert 'auto_approve' in classified
        assert 'max_attempts' in classified

    def test_preapproved_patterns_contains_missing_readme(self):
        """Verify preapproved patterns includes missing_readme."""
        prioritiser = Prioritiser()

        assert 'missing_readme' in prioritiser.PREAPPROVED_PATTERNS
        pattern = prioritiser.PREAPPROVED_PATTERNS['missing_readme']
        assert pattern['risk_level'] == 'LOW'
        assert pattern['auto_approve'] is True
        assert pattern['max_attempts'] == 3

    def test_classify_multiple_findings_independently(self):
        """Verify multiple findings are classified independently."""
        prioritiser = Prioritiser()

        finding1 = {'type': 'missing_readme', 'id': '1'}
        finding2 = {'type': 'unknown_issue', 'id': '2'}

        classified1 = prioritiser.classify_finding(finding1)
        classified2 = prioritiser.classify_finding(finding2)

        assert classified1['auto_approve'] is True
        assert classified2['auto_approve'] is False


class TestPlannerTaskGeneration:
    """Test repair task planning and generation."""

    def test_plan_readme_repair_task(self):
        """Verify planning of README repair task."""
        planner = Planner()
        finding = {
            'type': 'missing_readme',
            'path': '/repo',
            'risk_level': 'LOW',
            'auto_approve': True,
            'max_attempts': 3,
            'finding_id': 'finding_123',
        }

        task = planner.create_repair_plan(finding)

        assert task['type'] == 'missing_readme'
        assert task['action'] == 'generate_readme'
        assert task['repo_path'] == '/repo'
        assert task['risk_level'] == 'LOW'

    def test_plan_generates_unique_task_id(self):
        """Verify each task gets a unique task_id."""
        planner = Planner()
        finding1 = {
            'type': 'missing_readme',
            'path': '/repo1',
            'risk_level': 'LOW',
            'auto_approve': True,
            'max_attempts': 3,
        }
        finding2 = {
            'type': 'missing_readme',
            'path': '/repo2',
            'risk_level': 'LOW',
            'auto_approve': True,
            'max_attempts': 3,
        }

        task1 = planner.create_repair_plan(finding1)
        task2 = planner.create_repair_plan(finding2)

        assert task1['task_id'] != task2['task_id']
        assert task1['task_id'].startswith('readme_')
        assert task2['task_id'].startswith('readme_')

    def test_plan_includes_sandbox_branch(self):
        """Verify task includes sandbox branch name."""
        planner = Planner()
        finding = {
            'type': 'missing_readme',
            'path': '/repo',
            'risk_level': 'LOW',
            'auto_approve': True,
            'max_attempts': 3,
        }

        task = planner.create_repair_plan(finding)

        assert 'sandbox_branch' in task
        assert 'studio/repair/' in task['sandbox_branch']

    def test_plan_includes_acceptance_criteria(self):
        """Verify task includes acceptance criteria."""
        planner = Planner()
        finding = {
            'type': 'missing_readme',
            'path': '/repo',
            'risk_level': 'LOW',
            'auto_approve': True,
            'max_attempts': 3,
        }

        task = planner.create_repair_plan(finding)

        assert 'acceptance_criteria' in task
        assert isinstance(task['acceptance_criteria'], list)
        assert len(task['acceptance_criteria']) >= 3
        assert any('README' in criterion for criterion in task['acceptance_criteria'])

    def test_plan_includes_timestamp(self):
        """Verify task includes creation timestamp."""
        planner = Planner()
        finding = {
            'type': 'missing_readme',
            'path': '/repo',
            'risk_level': 'LOW',
            'auto_approve': True,
            'max_attempts': 3,
        }

        task = planner.create_repair_plan(finding)

        assert 'created_at' in task
        # Should be ISO format
        assert 'T' in task['created_at']

    def test_plan_preserves_finding_id(self):
        """Verify task includes finding_id from original finding."""
        planner = Planner()
        finding = {
            'type': 'missing_readme',
            'path': '/repo',
            'risk_level': 'LOW',
            'auto_approve': True,
            'max_attempts': 3,
            'finding_id': 'finding_abc123',
        }

        task = planner.create_repair_plan(finding)

        assert task['finding_id'] == 'finding_abc123'

    def test_plan_unknown_finding_type_raises(self):
        """Verify planning unknown finding type raises ValueError."""
        planner = Planner()
        finding = {
            'type': 'unknown_type',
            'path': '/repo',
            'risk_level': 'UNKNOWN',
            'auto_approve': False,
            'max_attempts': 0,
        }

        with pytest.raises(ValueError, match="No repair plan"):
            planner.create_repair_plan(finding)

    def test_plan_task_includes_all_finding_metadata(self):
        """Verify task includes risk and approval metadata."""
        planner = Planner()
        finding = {
            'type': 'missing_readme',
            'path': '/repo',
            'risk_level': 'LOW',
            'auto_approve': True,
            'max_attempts': 3,
        }

        task = planner.create_repair_plan(finding)

        assert task['risk_level'] == 'LOW'
        assert task['auto_approve'] is True
        assert task['max_attempts'] == 3

    def test_plan_missing_optional_fields(self):
        """Verify planning works with minimal finding data."""
        planner = Planner()
        finding = {
            'type': 'missing_readme',
            'path': '/repo',
        }

        task = planner.create_repair_plan(finding)

        assert task['type'] == 'missing_readme'
        assert task['repo_path'] == '/repo'
        # Missing fields should get defaults
        assert task['risk_level'] == 'UNKNOWN'
        assert task['auto_approve'] is False


class TestPlannerAndPrioritiserIntegration:
    """Test integration of Prioritiser and Planner."""

    def test_full_workflow_classify_and_plan(self):
        """Verify complete workflow from finding to task."""
        prioritiser = Prioritiser()
        planner = Planner()

        # Step 1: Raw finding from scanner
        raw_finding = {
            'type': 'missing_readme',
            'path': '/repo',
            'severity': 'LOW',
            'finding_id': 'find_001',
        }

        # Step 2: Classify
        classified = prioritiser.classify_finding(raw_finding)
        assert classified['risk_level'] == 'LOW'

        # Step 3: Plan
        task = planner.create_repair_plan(classified)

        # Step 4: Verify result
        assert task['task_id'].startswith('readme_')
        assert task['type'] == 'missing_readme'
        assert task['risk_level'] == 'LOW'
        assert task['auto_approve'] is True

    def test_workflow_with_unknown_finding(self):
        """Verify workflow handles unknown findings correctly."""
        prioritiser = Prioritiser()
        planner = Planner()

        raw_finding = {
            'type': 'unknown_issue',
            'path': '/repo',
        }

        classified = prioritiser.classify_finding(raw_finding)
        assert classified['auto_approve'] is False

        # Planning should raise for unknown type
        with pytest.raises(ValueError):
            planner.create_repair_plan(classified)


class TestPrioritiserEdgeCases:
    """Test edge cases in prioritiser."""

    def test_classify_with_extra_fields(self):
        """Verify classification preserves extra fields."""
        prioritiser = Prioritiser()
        finding = {
            'type': 'missing_readme',
            'path': '/repo',
            'custom_field': 'custom_value',
            'priority': 'high',
        }

        classified = prioritiser.classify_finding(finding)

        assert classified['custom_field'] == 'custom_value'
        assert classified['priority'] == 'high'

    def test_classify_empty_finding_type(self):
        """Verify classification of empty finding type."""
        prioritiser = Prioritiser()
        finding = {
            'type': '',
            'path': '/repo',
        }

        classified = prioritiser.classify_finding(finding)

        assert classified['risk_level'] == 'UNKNOWN'
        assert classified['auto_approve'] is False


class TestPlannerEdgeCases:
    """Test edge cases in planner."""

    def test_plan_with_special_characters_in_path(self):
        """Verify planning works with special characters in repo path."""
        planner = Planner()
        finding = {
            'type': 'missing_readme',
            'path': '/repo-with-dashes/and_underscores',
            'risk_level': 'LOW',
            'auto_approve': True,
            'max_attempts': 3,
        }

        task = planner.create_repair_plan(finding)

        assert task['repo_path'] == '/repo-with-dashes/and_underscores'

    def test_plan_task_ids_are_short(self):
        """Verify task IDs are reasonably short and readable."""
        planner = Planner()
        finding = {
            'type': 'missing_readme',
            'path': '/repo',
            'risk_level': 'LOW',
            'auto_approve': True,
            'max_attempts': 3,
        }

        task = planner.create_repair_plan(finding)

        # Task ID should be readme_XXXXXXXX (16 chars total)
        assert len(task['task_id']) < 30
        assert 'readme_' in task['task_id']
