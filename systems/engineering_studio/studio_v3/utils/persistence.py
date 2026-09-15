"""State persistence and recovery"""
import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timezone

class StatePersistence:
    """Save and restore system state"""

    def __init__(self, state_dir: str = '.studio_state'):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)

    def save_state(self, state: Dict[str, Any]):
        """Save current state"""
        state_file = self.state_dir / f"state_{datetime.now(timezone.utc).isoformat()}.json"
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)

        # Keep latest
        latest = self.state_dir / 'latest.json'
        latest.write_text(json.dumps(state, indent=2))

    def load_state(self) -> Dict[str, Any]:
        """Load latest state"""
        latest = self.state_dir / 'latest.json'
        if latest.exists():
            with open(latest) as f:
                return json.load(f)
        return {}

    def checkpoint(self, cycle_num: int, data: Dict[str, Any]):
        """Create checkpoint for recovery"""
        checkpoint_file = self.state_dir / f"checkpoint_{cycle_num}.json"
        with open(checkpoint_file, 'w') as f:
            json.dump({'cycle': cycle_num, 'data': data}, f, indent=2)

    def recover_from_checkpoint(self, cycle_num: int) -> Dict[str, Any]:
        """Recover from checkpoint"""
        checkpoint_file = self.state_dir / f"checkpoint_{cycle_num}.json"
        if checkpoint_file.exists():
            with open(checkpoint_file) as f:
                return json.load(f).get('data', {})
        return {}
