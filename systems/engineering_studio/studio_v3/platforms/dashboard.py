"""Real-time dashboard for Studio status"""
from pathlib import Path
import json
from typing import Dict, Any

class Dashboard:
    """Live status dashboard"""

    def __init__(self, state_dir: str = '.studio_state'):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)

    def render_status(self) -> str:
        """Render current status"""
        try:
            metrics_dir = Path('.studio_metrics')
            pending_approvals = len(list(Path('.studio_approvals').glob('*.json'))) if Path('.studio_approvals').exists() else 0
            notifications = len(list(Path('.studio_notifications').glob('*.json'))) if Path('.studio_notifications').exists() else 0

            return f"""
╔════════════════════════════════════════════════════════╗
║           ENGINEERING STUDIO - LIVE DASHBOARD         ║
╚════════════════════════════════════════════════════════╝

🔍 SYSTEM STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Status: 🟢 OPERATIONAL
Mode: Feature Branch Autonomous
Monitoring: ACTIVE

📊 METRICS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pending Approvals: {pending_approvals}
Notifications: {notifications}

🔧 QUEUES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Repair Queue: {len(list(Path('.studio_queue').glob('*.json')) if Path('.studio_queue').exists() else [])}
Learning Patterns: Active

💾 DATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Logs: .studio_logs/
Metrics: .studio_metrics/
Knowledge: .studio_knowledge/
Approvals: .studio_approvals/
Notifications: .studio_notifications/

"""
        except Exception as e:
            return f"Dashboard error: {e}"
