"""
Benchmark Tracker: Tracks performance and quality metrics over time.
Measures frontier research impact on system performance.
"""

from typing import Dict, List, Any
from datetime import datetime


class BenchmarkTracker:
    """Tracks system benchmarks and metrics."""

    def __init__(self):
        self.benchmarks = []

    def record_benchmark(self, metric_name: str, value: float,
                         context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Record a benchmark measurement."""
        record = {
            'timestamp': datetime.now().isoformat(),
            'metric': metric_name,
            'value': value,
            'context': context or {},
            'baseline': self._get_baseline(metric_name)
        }
        record['trend'] = self._calculate_trend(metric_name, value)
        self.benchmarks.append(record)
        return record

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of tracked metrics.

        health_status/alerts previously were hardcoded to always report
        'good'/empty regardless of what had actually been recorded. They
        now reflect the real recorded benchmarks: any 'degrading' trend
        produces an alert and a non-good status.
        """
        alerts = [
            f"{b['metric']} degrading: {b['value']} vs baseline {b['baseline']}"
            for b in self.benchmarks if b.get('trend') == 'degrading'
        ]
        return {
            'timestamp': datetime.now().isoformat(),
            'total_measurements': len(self.benchmarks),
            'tracked_metrics': [
                'cycle_latency_ms',
                'memory_usage_mb',
                'accuracy_score',
                'learning_efficiency'
            ],
            'health_status': 'degrading' if alerts else ('no_data' if not self.benchmarks else 'stable'),
            'alerts': alerts
        }

    def _get_baseline(self, metric_name: str) -> float:
        """Get baseline value for metric."""
        baselines = {
            'cycle_latency_ms': 50.0,
            'memory_usage_mb': 256.0,
            'accuracy_score': 0.85,
            'learning_efficiency': 0.75
        }
        return baselines.get(metric_name, 0.0)

    def _calculate_trend(self, metric_name: str, value: float) -> str:
        """Calculate trend compared to baseline."""
        baseline = self._get_baseline(metric_name)
        if value < baseline * 0.9:
            return 'improving'
        elif value > baseline * 1.1:
            return 'degrading'
        else:
            return 'stable'


def record_benchmark(metric_name: str, value: float,
                     context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Module-level benchmark recorder."""
    tracker = BenchmarkTracker()
    return tracker.record_benchmark(metric_name, value, context)
