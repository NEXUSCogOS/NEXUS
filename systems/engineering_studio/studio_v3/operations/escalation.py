"""Escalation engine for MEDIUM/HIGH risk tasks requiring human intervention"""
from typing import Dict, Any, List
from datetime import datetime, timezone

class EscalationEngine:
    """Route tasks to human intervention when autonomy isn't safe"""

    ESCALATION_RULES = {
        'MEDIUM': {
            'timeout': 3600,  # 1 hour to wait for approval
            'notify': True,
            'action': 'pause_and_notify'
        },
        'HIGH': {
            'timeout': 86400,  # 24 hours
            'notify': True,
            'action': 'escalate_immediately'
        },
        'CRITICAL': {
            'timeout': 0,  # No timeout - human must decide
            'notify': True,
            'action': 'block_and_escalate'
        }
    }

    def __init__(self, notification_handler=None):
        self.notification_handler = notification_handler
        self.pending_escalations = []

    def evaluate(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Determine if task needs escalation"""
        risk_level = task.get('risk_level', 'UNKNOWN')

        if risk_level not in self.ESCALATION_RULES:
            return {'escalate': False, 'reason': 'Unknown risk level'}

        rule = self.ESCALATION_RULES[risk_level]

        if rule['action'] in ['pause_and_notify', 'escalate_immediately', 'block_and_escalate']:
            return {
                'escalate': True,
                'risk_level': risk_level,
                'action': rule['action'],
                'timeout': rule['timeout'],
                'notify': rule['notify'],
                'task_id': task.get('task_id'),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

        return {'escalate': False, 'reason': f'{risk_level} risk approved for autonomous execution'}

    def notify(self, escalation: Dict[str, Any]) -> bool:
        """Send escalation notification"""
        if self.notification_handler:
            return self.notification_handler(escalation)
        return False

    def wait_for_approval(self, task_id: str, timeout: int) -> bool:
        """Wait for human approval (placeholder - integrate with actual approval system)"""
        # In production: query approval database/queue
        return False
