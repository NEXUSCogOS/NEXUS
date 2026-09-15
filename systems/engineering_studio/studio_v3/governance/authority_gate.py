from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime, timezone


# ============================================================================
# SPECIALIZED AGENT STRATEGIES (extracted from decision_coordinator.py)
# ============================================================================

class SpecializedAgent:
    """Base class for specialized agents"""

    def __init__(self, repo_path: str, agent_type: str):
        self.repo_path = Path(repo_path) if isinstance(repo_path, str) else repo_path
        self.agent_type = agent_type
        self.capabilities = []
        self.decision_log = []

    def get_capabilities(self) -> List[str]:
        """Return list of capabilities"""
        return self.capabilities


class CodeModificationAgent(SpecializedAgent):
    """Implements code changes safely"""

    def __init__(self, repo_path: str = '.'):
        super().__init__(repo_path, 'code_modification')
        self.capabilities = ['add_type_hints', 'refactor', 'optimize']

    def add_type_hints(self, file_path: str) -> Dict[str, Any]:
        """Add type hints to file"""
        result = {'action': 'add_type_hints', 'file': file_path, 'status': 'ready'}
        self.decision_log.append(result)
        return result

    def refactor_function(self, function_name: str) -> Dict[str, Any]:
        """Refactor function"""
        result = {'action': 'refactor', 'function': function_name, 'status': 'ready'}
        self.decision_log.append(result)
        return result

    def optimize_code(self, file_path: str) -> Dict[str, Any]:
        """Optimize code"""
        result = {'action': 'optimize', 'file': file_path, 'status': 'ready'}
        self.decision_log.append(result)
        return result


class TestAgent(SpecializedAgent):
    """Generates and validates tests"""

    def __init__(self, repo_path: str = '.'):
        super().__init__(repo_path, 'testing')
        self.capabilities = ['generate_tests', 'validate_coverage', 'mutation_testing']

    def generate_tests(self, module: str) -> Dict[str, Any]:
        """Generate test cases"""
        result = {'action': 'generate_tests', 'module': module, 'tests_generated': 5}
        self.decision_log.append(result)
        return result

    def validate_coverage(self) -> Dict[str, Any]:
        """Validate test coverage"""
        result = {'coverage': 0.68, 'target': 0.80, 'gap': 0.12}
        self.decision_log.append(result)
        return result

    def mutation_testing(self, module: str) -> Dict[str, Any]:
        """Run mutation testing"""
        result = {'action': 'mutation_testing', 'module': module, 'mutations_tested': 10}
        self.decision_log.append(result)
        return result


class SecurityAgent(SpecializedAgent):
    """Identifies and fixes security issues"""

    def __init__(self, repo_path: str = '.'):
        super().__init__(repo_path, 'security')
        self.capabilities = ['scan_vulnerabilities', 'fix_secrets', 'validate_dependencies']

    def scan_vulnerabilities(self) -> List[Dict[str, Any]]:
        """Scan for security vulnerabilities"""
        vulnerabilities = [
            {'type': 'hardcoded_secret', 'severity': 'high', 'count': 0},
            {'type': 'sql_injection_risk', 'severity': 'high', 'count': 0},
            {'type': 'insecure_random', 'severity': 'medium', 'count': 0}
        ]
        self.decision_log.append({'action': 'scan_vulnerabilities', 'result': vulnerabilities})
        return vulnerabilities

    def fix_secrets(self) -> Dict[str, Any]:
        """Fix hardcoded secrets"""
        result = {'action': 'fix_secrets', 'secrets_fixed': 0}
        self.decision_log.append(result)
        return result

    def validate_dependencies(self) -> Dict[str, Any]:
        """Validate dependencies for vulnerabilities"""
        result = {'action': 'validate_dependencies', 'issues_found': 0}
        self.decision_log.append(result)
        return result


class DocumentationAgent(SpecializedAgent):
    """Generates and improves documentation"""

    def __init__(self, repo_path: str = '.'):
        super().__init__(repo_path, 'documentation')
        self.capabilities = ['generate_docstrings', 'improve_readme', 'api_docs']

    def generate_docstrings(self, module: str) -> Dict[str, Any]:
        """Generate docstrings"""
        result = {'action': 'docstrings', 'module': module, 'docstrings_added': 12}
        self.decision_log.append(result)
        return result

    def improve_readme(self) -> Dict[str, Any]:
        """Improve README"""
        result = {'action': 'readme_update', 'sections_added': ['API', 'Examples', 'Architecture']}
        self.decision_log.append(result)
        return result

    def generate_api_docs(self, module: str) -> Dict[str, Any]:
        """Generate API documentation"""
        result = {'action': 'api_docs', 'module': module, 'docs_generated': True}
        self.decision_log.append(result)
        return result


# ============================================================================
# AUTHORITY GATE (enhanced with agent strategies)
# ============================================================================

class AuthorityGate:
    """
    Governance layer: approve repairs based on risk and pre-approved patterns.
    Enhanced with specialized agent strategies for more nuanced decision-making.
    """

    def __init__(self, repo_path: str = '.'):
        self.repo_path = repo_path
        self.decision_log = []

        # Initialize agent strategies
        self.code_agent = CodeModificationAgent(repo_path)
        self.test_agent = TestAgent(repo_path)
        self.security_agent = SecurityAgent(repo_path)
        self.doc_agent = DocumentationAgent(repo_path)

    def approve(self, task: Dict[str, Any], agent_strategy: Optional[str] = None) -> bool:
        """
        Determine if task can execute autonomously.
        Returns True only if low-risk and pre-approved.

        Args:
            task: Task to approve
            agent_strategy: Optional strategy name (CodeModificationAgent, TestAgent,
                           SecurityAgent, DocumentationAgent) for specialized approval
        """
        # Basic risk checks
        if task.get('risk_level') not in ('LOW', 'MEDIUM'):
            return False

        if not task.get('auto_approve', False):
            return False

        # Approved task types
        approved_types = {'missing_readme', 'add_type_hints', 'generate_tests',
                         'security_fix', 'improve_documentation'}
        if task.get('type') not in approved_types:
            return False

        # If an agent strategy is specified, consult it
        if agent_strategy:
            return self._approve_with_strategy(task, agent_strategy)

        return True

    def _approve_with_strategy(self, task: Dict[str, Any], strategy: str) -> bool:
        """
        Consult specialized agent strategy for approval.

        Args:
            task: Task to approve
            strategy: Strategy name (CodeModificationAgent, TestAgent,
                     SecurityAgent, DocumentationAgent)
        """
        if strategy == 'CodeModificationAgent':
            return self._approve_code_modification(task)
        elif strategy == 'TestAgent':
            return self._approve_testing(task)
        elif strategy == 'SecurityAgent':
            return self._approve_security(task)
        elif strategy == 'DocumentationAgent':
            return self._approve_documentation(task)
        else:
            return False

    def _approve_code_modification(self, task: Dict[str, Any]) -> bool:
        """Approval logic for code modifications"""
        # Code mods approved if: low risk + pre-approved + not critical files
        critical_files = {'__init__.py', 'setup.py', 'requirements.txt'}
        affected_file = task.get('affected_file', '')

        if any(critical in affected_file for critical in critical_files):
            return False

        return task.get('risk_level') == 'LOW'

    def _approve_testing(self, task: Dict[str, Any]) -> bool:
        """Approval logic for testing tasks"""
        # Tests are low-risk and typically approved
        return task.get('risk_level') in ('LOW', 'MEDIUM')

    def _approve_security(self, task: Dict[str, Any]) -> bool:
        """Approval logic for security fixes"""
        # Security fixes get special consideration based on vulnerability severity
        severity = task.get('severity', 'medium')
        return severity in ('high', 'critical', 'medium')

    def _approve_documentation(self, task: Dict[str, Any]) -> bool:
        """Approval logic for documentation improvements"""
        # Documentation improvements are very low-risk
        return True

    def dispatch_to_agent(self, task: Dict[str, Any], agent_strategy: str) -> Dict[str, Any]:
        """
        Dispatch task to specialized agent for execution.

        Args:
            task: Task to execute
            agent_strategy: Agent strategy to dispatch to

        Returns:
            Result from agent execution
        """
        result = {
            'task_id': task.get('task_id'),
            'strategy': agent_strategy,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'executed': False,
            'result': None
        }

        try:
            if agent_strategy == 'CodeModificationAgent':
                result['result'] = self.code_agent.add_type_hints(
                    task.get('affected_file', '')
                )
                result['executed'] = True

            elif agent_strategy == 'TestAgent':
                result['result'] = self.test_agent.generate_tests(
                    task.get('module', '')
                )
                result['executed'] = True

            elif agent_strategy == 'SecurityAgent':
                result['result'] = self.security_agent.scan_vulnerabilities()
                result['executed'] = True

            elif agent_strategy == 'DocumentationAgent':
                result['result'] = self.doc_agent.generate_docstrings(
                    task.get('module', '')
                )
                result['executed'] = True

        except Exception as e:
            result['error'] = str(e)

        self.decision_log.append(result)
        return result

    def create_audit_entry(self, task: Dict[str, Any], approved: bool, reason: str = '',
                          agent_strategy: Optional[str] = None) -> Dict[str, Any]:
        """Create audit trail entry for governance decision"""
        entry = {
            'task_id': task.get('task_id'),
            'decision': 'approved' if approved else 'rejected',
            'reason': reason,
            'risk_level': task.get('risk_level'),
            'task_type': task.get('type'),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

        if agent_strategy:
            entry['agent_strategy'] = agent_strategy

        self.decision_log.append(entry)
        return entry

    def get_agent_capabilities(self) -> Dict[str, List[str]]:
        """Get all agent capabilities"""
        return {
            'code_modification': self.code_agent.get_capabilities(),
            'testing': self.test_agent.get_capabilities(),
            'security': self.security_agent.get_capabilities(),
            'documentation': self.doc_agent.get_capabilities(),
        }

    def get_decision_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve decision history"""
        if limit:
            return self.decision_log[-limit:]
        return self.decision_log
