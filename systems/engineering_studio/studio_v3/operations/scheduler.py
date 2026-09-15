"""Task scheduling and batch processing"""
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timezone

class TaskScheduler:
    """Schedule and batch repair tasks"""
    
    def __init__(self, queue_dir: str = '.studio_queue'):
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(exist_ok=True)
    
    def schedule_repair(self, task: Dict[str, Any]) -> str:
        """Add task to repair queue"""
        task_id = task.get('task_id')
        task_file = self.queue_dir / f"{task_id}.json"
        
        task['scheduled_at'] = datetime.now(timezone.utc).isoformat()
        task['status'] = 'scheduled'
        
        with open(task_file, 'w') as f:
            json.dump(task, f, indent=2)
        return task_id
    
    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """Get all scheduled tasks"""
        tasks = []
        for task_file in self.queue_dir.glob("*.json"):
            with open(task_file) as f:
                tasks.append(json.load(f))
        return sorted(tasks, key=lambda t: t.get('priority', 0), reverse=True)
    
    def mark_complete(self, task_id: str):
        """Mark task as completed"""
        task_file = self.queue_dir / f"{task_id}.json"
        if task_file.exists():
            task_file.unlink()
