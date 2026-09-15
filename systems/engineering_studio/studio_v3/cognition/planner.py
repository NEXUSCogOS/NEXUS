import uuid
from datetime import datetime, timezone
from typing import Dict, Any

class Planner:
    def create_repair_plan(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert classified finding into actionable repair task
        """
        finding_type = finding['type']

        if finding_type == 'missing_readme':
            return self._plan_readme_repair(finding)
        else:
            raise ValueError(f"No repair plan for {finding_type}")

    def _plan_readme_repair(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        """Plan autonomous README generation"""
        repo_path = finding['path']
        task_id = f"readme_{uuid.uuid4().hex[:8]}"

        return {
            'task_id': task_id,
            'finding_id': finding.get('finding_id'),
            'type': 'missing_readme',
            'action': 'generate_readme',
            'sandbox_branch': f'studio/repair/{task_id}',
            'repo_path': repo_path,
            'risk_level': finding.get('risk_level', 'UNKNOWN'),
            'auto_approve': finding.get('auto_approve', False),
            'max_attempts': finding.get('max_attempts', 0),
            'acceptance_criteria': [
                'README.md created in repository root',
                'File contains project title and description',
                'pytest runs without syntax errors',
                'Changes committed with repair audit trail'
            ],
            'created_at': datetime.now(timezone.utc).isoformat(),
        }
