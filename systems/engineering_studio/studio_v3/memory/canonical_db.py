import sqlite3
from pathlib import Path
import yaml
import json
from datetime import datetime, timezone

class CanonicalDB:
    def __init__(self, config_path: str):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        self.canonical = self.config['canonical']

    def connect(self, db_name: str) -> sqlite3.Connection:
        """Connect to canonical database (evidence, repair, executive, strategic, proposals)"""
        db_key = f'{db_name}_db'
        if db_key not in self.canonical:
            raise ValueError(f"Unknown database: {db_name}")
        path = self.canonical[db_key]
        return sqlite3.connect(path)

    def log_repair(self, task_id: str, status: str, details: dict) -> None:
        """Write repair attempt to canonical repair_memory.db"""
        conn = self.connect('repair')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO repair_attempts
            (task_id, status, timestamp, details, audit_trail)
            VALUES (?, ?, ?, ?, ?)
        ''', (task_id, status, datetime.now(timezone.utc).isoformat(),
              json.dumps(details), json.dumps({
                  'action': status,
                  'timestamp': datetime.now(timezone.utc).isoformat()
              })))
        conn.commit()
        conn.close()

    def get_backpressure_state(self) -> dict:
        """Read current backpressure state"""
        path = Path(self.canonical['backpressure_state'])
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return {'paused': False, 'reason': None}

canonical_db = None

def init_canonical(config_path: str):
    global canonical_db
    canonical_db = CanonicalDB(config_path)
    return canonical_db
