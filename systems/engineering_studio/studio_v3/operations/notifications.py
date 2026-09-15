"""Notification system for important events"""
from typing import Dict, Any
from pathlib import Path
import json
from datetime import datetime, timezone

class NotificationSystem:
    """Send notifications for events"""
    
    def __init__(self, log_dir: str = '.studio_notifications'):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
    
    def notify_escalation(self, task: Dict[str, Any], reason: str):
        """Notify about escalated task"""
        notification = {
            'type': 'escalation',
            'severity': task.get('risk_level'),
            'task_id': task.get('task_id'),
            'reason': reason,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'action_required': True
        }
        self._log_notification(notification)
    
    def notify_repair_success(self, task_id: str):
        """Notify successful repair"""
        notification = {
            'type': 'success',
            'task_id': task_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'action_required': False
        }
        self._log_notification(notification)
    
    def notify_repair_failure(self, task_id: str, error: str):
        """Notify repair failure"""
        notification = {
            'type': 'failure',
            'task_id': task_id,
            'error': error,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'action_required': True
        }
        self._log_notification(notification)
    
    def _log_notification(self, notification: Dict[str, Any]):
        """Log notification"""
        notif_file = self.log_dir / f"{notification['task_id']}_{notification['type']}.json"
        with open(notif_file, 'w') as f:
            json.dump(notification, f, indent=2)
