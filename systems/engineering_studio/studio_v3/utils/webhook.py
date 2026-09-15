"""Webhook system for external integrations"""
from typing import Dict, Any, Callable
import json
from pathlib import Path
from datetime import datetime, timezone

class WebhookSystem:
    """Manage webhooks for Studio events"""

    def __init__(self, webhook_dir: str = '.studio_webhooks'):
        self.webhook_dir = Path(webhook_dir)
        self.webhook_dir.mkdir(exist_ok=True)
        self.handlers: Dict[str, list] = {
            'repair_success': [],
            'repair_failure': [],
            'escalation': [],
            'cycle_complete': []
        }

    def register_handler(self, event: str, handler: Callable):
        """Register webhook handler"""
        if event not in self.handlers:
            self.handlers[event] = []
        self.handlers[event].append(handler)

    def trigger(self, event: str, data: Dict[str, Any]):
        """Trigger webhook handlers"""
        if event not in self.handlers:
            return

        for handler in self.handlers[event]:
            try:
                handler(data)
            except Exception as e:
                print(f"Webhook handler error: {e}")

    def log_event(self, event: str, data: Dict[str, Any]):
        """Log webhook event"""
        event_file = self.webhook_dir / f"{event}_{datetime.now(timezone.utc).isoformat()}.json"
        with open(event_file, 'w') as f:
            json.dump({'event': event, 'data': data}, f, indent=2)
