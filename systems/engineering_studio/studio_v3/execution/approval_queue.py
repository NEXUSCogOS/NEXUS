"""Queue for tasks requiring human approval"""
from pathlib import Path
from typing import Dict, Any, List
import json
from datetime import datetime, timezone

class ApprovalQueue:
    """Manage tasks waiting for human approval"""
    
    def __init__(self, queue_dir: str = '.studio_approvals'):
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(exist_ok=True)
    
    def add_to_queue(self, task: Dict[str, Any], reason: str):
        """Add task requiring approval"""
        task_id = task.get('task_id')
        approval_file = self.queue_dir / f"{task_id}.json"
        
        approval_task = {
            'task_id': task_id,
            'task_type': task.get('type'),
            'risk_level': task.get('risk_level'),
            'reason': reason,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'details': task,
            'status': 'pending'
        }
        
        with open(approval_file, 'w') as f:
            json.dump(approval_task, f, indent=2)
    
    def get_pending(self) -> List[Dict[str, Any]]:
        """Get all pending approvals"""
        pending = []
        for f in self.queue_dir.glob("*.json"):
            with open(f) as fp:
                pending.append(json.load(fp))
        return pending
    
    def approve(self, task_id: str):
        """Approve a task"""
        f = self.queue_dir / f"{task_id}.json"
        if f.exists():
            data = json.loads(f.read_text())
            data['status'] = 'approved'
            data['approved_at'] = datetime.now(timezone.utc).isoformat()
            f.write_text(json.dumps(data, indent=2))
    
    def reject(self, task_id: str):
        """Reject a task"""
        f = self.queue_dir / f"{task_id}.json"
        if f.exists():
            f.unlink()
