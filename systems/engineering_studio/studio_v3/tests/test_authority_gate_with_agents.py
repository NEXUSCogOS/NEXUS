"""
Tests for enhanced AuthorityGate with specialized agent strategies.

This test suite verifies:
1. Agent strategy initialization and capabilities
2. Task approval with different strategies
3. Agent dispatch and execution
4. Audit trail creation
5. Decision logging
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from ..governance.authority_gate import (
    AuthorityGate,
    CodeModificationAgent,
    TestAgent,
    SecurityAgent,
    DocumentationAgent,
    SpecializedAgent
)


class TestSpecializedAgents:
    """Test individual specialized agent strategies"""

    def test_code_modification_agent_initialization(self):
        """Test CodeModificationAgent initializes correctly"""
        agent = CodeModificationAgent('/tmp/test_repo')
        assert agent.agent_type == 'code_modification'
        assert 'add_type_hints' in agent.capabilities
        assert 'refactor' in agent.capabilities
        assert 'optimize' in agent.capabilities
        assert len(agent.decision_log) == 0

    def test_code_modification_agent_add_type_hints(self):
        """Test CodeModificationAgent add_type_hints action"""
        agent = CodeModificationAgent('/tmp/test_repo')
        result = agent.add_type_hints('core.py')

        assert result['action'] == 'add_type_hints'
        assert result['file'] == 'core.py'
        assert result['status'] == 'ready'
        assert len(agent.decision_log) == 1

    def test_test_agent_initialization(self):
        """Test TestAgent initializes correctly"""
        agent = TestAgent('/tmp/test_repo')
        assert agent.agent_type == 'testing'
        assert 'generate_tests' in agent.capabilities
        assert 'validate_coverage' in agent.capabilities
        assert 'mutation_testing' in agent.capabilities

    def test_test_agent_generate_tests(self):
        """Test TestAgent generate_tests action"""
        agent = TestAgent('/tmp/test_repo')
        result = agent.generate_tests('core_module')

        assert result['action'] == 'generate_tests'
        assert result['module'] == 'core_module'
        assert result['tests_generated'] == 5

    def test_test_agent_validate_coverage(self):
        """Test TestAgent validate_coverage action"""
        agent = TestAgent('/tmp/test_repo')
        result = agent.validate_coverage()

        assert 'coverage' in result
        assert 'target' in result
        assert result['coverage'] == 0.68
        assert result['target'] == 0.80

    def test_security_agent_initialization(self):
        """Test SecurityAgent initializes correctly"""
        agent = SecurityAgent('/tmp/test_repo')
        assert agent.agent_type == 'security'
        assert 'scan_vulnerabilities' in agent.capabilities
        assert 'fix_secrets' in agent.capabilities
        assert 'validate_dependencies' in agent.capabilities

    def test_security_agent_scan_vulnerabilities(self):
        """Test SecurityAgent scan_vulnerabilities action"""
        agent = SecurityAgent('/tmp/test_repo')
        result = agent.scan_vulnerabilities()

        assert isinstance(result, list)
        assert len(result) > 0
        assert any(v['type'] == 'hardcoded_secret' for v in result)

    def test_documentation_agent_initialization(self):
        """Test DocumentationAgent initializes correctly"""
        agent = DocumentationAgent('/tmp/test_repo')
        assert agent.agent_type == 'documentation'
        assert 'generate_docstrings' in agent.capabilities
        assert 'improve_readme' in agent.capabilities
        assert 'api_docs' in agent.capabilities

    def test_documentation_agent_generate_docstrings(self):
        """Test DocumentationAgent generate_docstrings action"""
        agent = DocumentationAgent('/tmp/test_repo')
        result = agent.generate_docstrings('core')

        assert result['action'] == 'docstrings'
        assert result['module'] == 'core'
        assert result['docstrings_added'] == 12

    def test_agent_get_capabilities(self):
        """Test agent get_capabilities method"""
        agents = [
            CodeModificationAgent('/tmp'),
            TestAgent('/tmp'),
            SecurityAgent('/tmp'),
            DocumentationAgent('/tmp')
        ]

        for agent in agents:
            caps = agent.get_capabilities()
            assert isinstance(caps, list)
            assert len(caps) > 0


class TestAuthorityGateBasic:
    """Test basic AuthorityGate functionality"""

    def test_authority_gate_initialization(self):
        """Test AuthorityGate initializes with agents"""
        gate = AuthorityGate('/tmp/test_repo')

        assert gate.repo_path == '/tmp/test_repo'
        assert isinstance(gate.code_agent, CodeModificationAgent)
        assert isinstance(gate.test_agent, TestAgent)
        assert isinstance(gate.security_agent, SecurityAgent)
        assert isinstance(gate.doc_agent, DocumentationAgent)
        assert len(gate.decision_log) == 0

    def test_approve_low_risk_auto_approved_task(self):
        """Test approval of low-risk, pre-approved tasks"""
        gate = AuthorityGate()

        task = {
            'task_id': 'test_001',
            'type': 'missing_readme',
            'risk_level': 'LOW',
            'auto_approve': True
        }

        assert gate.approve(task) is True

    def test_deny_high_risk_task(self):
        """Test rejection of high-risk tasks"""
        gate = AuthorityGate()

        task = {
            'task_id': 'test_002',
            'type': 'missing_readme',
            'risk_level': 'HIGH',
            'auto_approve': True
        }

        assert gate.approve(task) is False

    def test_deny_unapproved_task(self):
        """Test rejection of non-pre-approved tasks"""
        gate = AuthorityGate()

        task = {
            'task_id': 'test_003',
            'type': 'missing_readme',
            'risk_level': 'LOW',
            'auto_approve': False
        }

        assert gate.approve(task) is False

    def test_deny_unknown_task_type(self):
        """Test rejection of unknown task types"""
        gate = AuthorityGate()

        task = {
            'task_id': 'test_004',
            'type': 'unknown_type',
            'risk_level': 'LOW',
            'auto_approve': True
        }

        assert gate.approve(task) is False


class TestAuthorityGateWithStrategies:
    """Test AuthorityGate with agent strategies"""

    def test_approve_with_code_modification_strategy(self):
        """Test approval with CodeModificationAgent strategy"""
        gate = AuthorityGate()

        task = {
            'task_id': 'code_001',
            'type': 'add_type_hints',
            'risk_level': 'LOW',
            'auto_approve': True,
            'affected_file': 'utils.py'
        }

        assert gate.approve(task, agent_strategy='CodeModificationAgent') is True

    def test_deny_code_modification_critical_file(self):
        """Test denial of code modification on critical files"""
        gate = AuthorityGate()

        task = {
            'task_id': 'code_002',
            'type': 'add_type_hints',
            'risk_level': 'LOW',
            'auto_approve': True,
            'affected_file': 'setup.py'  # Critical file
        }

        assert gate.approve(task, agent_strategy='CodeModificationAgent') is False

    def test_approve_with_test_strategy(self):
        """Test approval with TestAgent strategy"""
        gate = AuthorityGate()

        task = {
            'task_id': 'test_001',
            'type': 'generate_tests',
            'risk_level': 'LOW',
            'auto_approve': True,
            'module': 'utils'
        }

        assert gate.approve(task, agent_strategy='TestAgent') is True

    def test_approve_medium_risk_testing(self):
        """Test approval of medium-risk testing tasks"""
        gate = AuthorityGate()

        task = {
            'task_id': 'test_002',
            'type': 'generate_tests',
            'risk_level': 'MEDIUM',
            'auto_approve': True,
            'module': 'core'
        }

        assert gate.approve(task, agent_strategy='TestAgent') is True

    def test_approve_with_security_strategy(self):
        """Test approval with SecurityAgent strategy"""
        gate = AuthorityGate()

        task = {
            'task_id': 'sec_001',
            'type': 'security_fix',
            'risk_level': 'MEDIUM',
            'auto_approve': True,
            'severity': 'high'
        }

        assert gate.approve(task, agent_strategy='SecurityAgent') is True

    def test_approve_with_documentation_strategy(self):
        """Test approval with DocumentationAgent strategy"""
        gate = AuthorityGate()

        task = {
            'task_id': 'doc_001',
            'type': 'improve_documentation',
            'risk_level': 'LOW',
            'auto_approve': True
        }

        assert gate.approve(task, agent_strategy='DocumentationAgent') is True

    def test_deny_invalid_strategy(self):
        """Test approval with invalid strategy"""
        gate = AuthorityGate()

        task = {
            'task_id': 'invalid_001',
            'type': 'add_type_hints',
            'risk_level': 'LOW',
            'auto_approve': True
        }

        assert gate.approve(task, agent_strategy='InvalidAgent') is False


class TestAgentDispatch:
    """Test agent dispatch functionality"""

    def test_dispatch_to_code_agent(self):
        """Test dispatching to CodeModificationAgent"""
        gate = AuthorityGate('/tmp/test_repo')

        task = {
            'task_id': 'dispatch_001',
            'affected_file': 'utils.py'
        }

        result = gate.dispatch_to_agent(task, 'CodeModificationAgent')

        assert result['task_id'] == 'dispatch_001'
        assert result['strategy'] == 'CodeModificationAgent'
        assert result['executed'] is True
        assert result['result'] is not None
        assert 'timestamp' in result

    def test_dispatch_to_test_agent(self):
        """Test dispatching to TestAgent"""
        gate = AuthorityGate()

        task = {
            'task_id': 'dispatch_002',
            'module': 'core'
        }

        result = gate.dispatch_to_agent(task, 'TestAgent')

        assert result['strategy'] == 'TestAgent'
        assert result['executed'] is True

    def test_dispatch_to_security_agent(self):
        """Test dispatching to SecurityAgent"""
        gate = AuthorityGate()

        task = {
            'task_id': 'dispatch_003'
        }

        result = gate.dispatch_to_agent(task, 'SecurityAgent')

        assert result['strategy'] == 'SecurityAgent'
        assert result['executed'] is True
        assert isinstance(result['result'], list)

    def test_dispatch_to_documentation_agent(self):
        """Test dispatching to DocumentationAgent"""
        gate = AuthorityGate()

        task = {
            'task_id': 'dispatch_004',
            'module': 'core'
        }

        result = gate.dispatch_to_agent(task, 'DocumentationAgent')

        assert result['strategy'] == 'DocumentationAgent'
        assert result['executed'] is True

    def test_dispatch_with_invalid_strategy(self):
        """Test dispatching with invalid strategy"""
        gate = AuthorityGate()

        task = {
            'task_id': 'dispatch_005'
        }

        result = gate.dispatch_to_agent(task, 'InvalidStrategy')

        assert result['executed'] is False


class TestAuditTrail:
    """Test audit trail and decision logging"""

    def test_create_audit_entry_approved(self):
        """Test creating audit entry for approved task"""
        gate = AuthorityGate()

        task = {
            'task_id': 'audit_001',
            'type': 'missing_readme',
            'risk_level': 'LOW'
        }

        entry = gate.create_audit_entry(task, approved=True, reason='Low risk task')

        assert entry['task_id'] == 'audit_001'
        assert entry['decision'] == 'approved'
        assert entry['reason'] == 'Low risk task'
        assert 'timestamp' in entry

    def test_create_audit_entry_rejected(self):
        """Test creating audit entry for rejected task"""
        gate = AuthorityGate()

        task = {
            'task_id': 'audit_002',
            'type': 'critical_change',
            'risk_level': 'HIGH'
        }

        entry = gate.create_audit_entry(task, approved=False, reason='High risk detected')

        assert entry['decision'] == 'rejected'
        assert entry['reason'] == 'High risk detected'

    def test_create_audit_entry_with_strategy(self):
        """Test creating audit entry with agent strategy"""
        gate = AuthorityGate()

        task = {
            'task_id': 'audit_003',
            'type': 'add_type_hints',
            'risk_level': 'LOW'
        }

        entry = gate.create_audit_entry(
            task, approved=True,
            reason='Approved by strategy',
            agent_strategy='CodeModificationAgent'
        )

        assert entry['agent_strategy'] == 'CodeModificationAgent'

    def test_decision_history_length(self):
        """Test decision history tracking"""
        gate = AuthorityGate()

        # Make multiple approval decisions
        for i in range(5):
            task = {
                'task_id': f'history_{i}',
                'type': 'missing_readme',
                'risk_level': 'LOW',
                'auto_approve': True
            }
            gate.approve(task)
            gate.create_audit_entry(task, approved=True)

        history = gate.get_decision_history()
        # Should have entries from both approve (logged internally) and create_audit_entry
        assert len(history) >= 5

    def test_decision_history_limit(self):
        """Test decision history with limit"""
        gate = AuthorityGate()

        # Add many entries
        for i in range(20):
            entry = gate.create_audit_entry(
                {'task_id': f'limited_{i}', 'type': 'test', 'risk_level': 'LOW'},
                approved=True
            )

        limited_history = gate.get_decision_history(limit=5)
        assert len(limited_history) == 5


class TestAgentCapabilities:
    """Test agent capability reporting"""

    def test_get_agent_capabilities(self):
        """Test retrieving all agent capabilities"""
        gate = AuthorityGate()

        capabilities = gate.get_agent_capabilities()

        assert 'code_modification' in capabilities
        assert 'testing' in capabilities
        assert 'security' in capabilities
        assert 'documentation' in capabilities

        assert 'add_type_hints' in capabilities['code_modification']
        assert 'generate_tests' in capabilities['testing']
        assert 'scan_vulnerabilities' in capabilities['security']
        assert 'generate_docstrings' in capabilities['documentation']

    def test_all_capabilities_are_lists(self):
        """Test that all capabilities are lists"""
        gate = AuthorityGate()

        capabilities = gate.get_agent_capabilities()

        for agent_name, agent_caps in capabilities.items():
            assert isinstance(agent_caps, list), f"{agent_name} capabilities not a list"


class TestIntegrationScenarios:
    """Integration tests for complete workflows"""

    def test_complete_code_modification_workflow(self):
        """Test complete code modification approval and dispatch workflow"""
        gate = AuthorityGate('/tmp/test_repo')

        # Create a code modification task
        task = {
            'task_id': 'workflow_001',
            'type': 'add_type_hints',
            'risk_level': 'LOW',
            'auto_approve': True,
            'affected_file': 'utils.py'
        }

        # Approve task
        approved = gate.approve(task, agent_strategy='CodeModificationAgent')
        assert approved is True

        # Create audit entry
        audit = gate.create_audit_entry(
            task, approved=True,
            reason='Code quality improvement',
            agent_strategy='CodeModificationAgent'
        )
        assert audit['decision'] == 'approved'

        # Dispatch to agent
        result = gate.dispatch_to_agent(task, 'CodeModificationAgent')
        assert result['executed'] is True

    def test_complete_security_workflow(self):
        """Test complete security task approval and execution"""
        gate = AuthorityGate()

        # Create a security task
        task = {
            'task_id': 'workflow_002',
            'type': 'security_fix',
            'risk_level': 'MEDIUM',
            'auto_approve': True,
            'severity': 'high'
        }

        # Approve with strategy
        approved = gate.approve(task, agent_strategy='SecurityAgent')
        assert approved is True

        # Dispatch
        result = gate.dispatch_to_agent(task, 'SecurityAgent')
        assert result['executed'] is True
        assert isinstance(result['result'], list)

    def test_multi_agent_coordination(self):
        """Test coordination of multiple agents"""
        gate = AuthorityGate()

        # Create multiple tasks of different types
        tasks = [
            {
                'task_id': 'multi_001',
                'type': 'add_type_hints',
                'risk_level': 'LOW',
                'auto_approve': True,
                'affected_file': 'core.py'
            },
            {
                'task_id': 'multi_002',
                'type': 'generate_tests',
                'risk_level': 'LOW',
                'auto_approve': True,
                'module': 'utils'
            },
            {
                'task_id': 'multi_003',
                'type': 'security_fix',
                'risk_level': 'MEDIUM',
                'auto_approve': True,
                'severity': 'high'
            }
        ]

        strategies = [
            'CodeModificationAgent',
            'TestAgent',
            'SecurityAgent'
        ]

        results = []
        for task, strategy in zip(tasks, strategies):
            approved = gate.approve(task, agent_strategy=strategy)
            if approved:
                result = gate.dispatch_to_agent(task, strategy)
                results.append(result)

        assert len(results) == 3
        assert all(r['executed'] for r in results)
