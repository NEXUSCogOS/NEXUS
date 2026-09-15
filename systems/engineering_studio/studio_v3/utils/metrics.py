"""Metrics collection and health monitoring"""
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

class MetricsCollector:
    """Track system health, repair success rate, and performance"""

    def __init__(self, metrics_dir: str = '.studio_metrics'):
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(exist_ok=True)
        self.current_metrics = {
            'start_time': datetime.now(timezone.utc).isoformat(),
            'cycles_total': 0,
            'findings_detected': 0,
            'repairs_attempted': 0,
            'repairs_successful': 0,
            'repairs_failed': 0,
            'escalations': 0,
            'cycle_times': []
        }

    def record_cycle(self, cycle_result: Dict[str, Any], duration_seconds: float):
        """Record metrics from a repair cycle"""
        self.current_metrics['cycles_total'] += 1
        self.current_metrics['findings_detected'] += len(cycle_result.get('findings', []))
        self.current_metrics['repairs_attempted'] += len(cycle_result.get('tasks_executed', [])) + len(cycle_result.get('failures', []))
        self.current_metrics['repairs_successful'] += len(cycle_result.get('tasks_executed', []))
        self.current_metrics['repairs_failed'] += len(cycle_result.get('failures', []))
        self.current_metrics['cycle_times'].append(duration_seconds)

    def get_health_status(self) -> Dict[str, Any]:
        """Return current system health"""
        success_rate = 0
        if self.current_metrics['repairs_attempted'] > 0:
            success_rate = self.current_metrics['repairs_successful'] / self.current_metrics['repairs_attempted']

        avg_cycle_time = sum(self.current_metrics['cycle_times']) / len(self.current_metrics['cycle_times']) if self.current_metrics['cycle_times'] else 0

        return {
            'cycles_completed': self.current_metrics['cycles_total'],
            'findings_fixed': self.current_metrics['repairs_successful'],
            'success_rate': f"{success_rate * 100:.1f}%",
            'avg_cycle_time': f"{avg_cycle_time:.1f}s",
            'uptime_since': self.current_metrics['start_time'],
            'status': 'HEALTHY' if success_rate > 0.8 else 'DEGRADED' if success_rate > 0.5 else 'POOR'
        }

    def save_metrics(self):
        """Persist metrics to disk"""
        metrics_file = self.metrics_dir / f"metrics_{datetime.now(timezone.utc).isoformat()}.json"
        with open(metrics_file, 'w') as f:
            json.dump(self.current_metrics, f, indent=2)
