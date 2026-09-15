"""Unified metrics collection and reporting system"""
import time
import logging
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timezone


class UnifiedMetrics:
    """Unified system for monitoring, metrics collection, and reporting"""

    def __init__(self, repo_path: str, record_dir: str = '.studio_metrics', interval_seconds: int = 300):
        self.repo_path = repo_path
        self.record_dir = Path(record_dir)
        self.record_dir.mkdir(exist_ok=True)
        self.interval = interval_seconds
        self.cycles = []
        self.current_cycle_data = None
        self.setup_logging()

    def setup_logging(self):
        """Configure logging"""
        log_dir = Path(self.repo_path) / '.studio_logs'
        log_dir.mkdir(exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / f'metrics_{datetime.now(timezone.utc).isoformat()}.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def start_cycle(self, cycle_num: int) -> Dict[str, Any]:
        """Start a monitoring/repair cycle"""
        self.current_cycle_data = {
            'cycle': cycle_num,
            'start_time': datetime.now(timezone.utc).isoformat(),
            'findings': [],
            'tasks_executed': [],
            'failures': [],
            'error': None
        }
        self.logger.info(f"Cycle {cycle_num} starting...")
        return self.current_cycle_data

    def record_findings(self, findings: List[Dict[str, Any]]):
        """Record cycle findings"""
        if self.current_cycle_data:
            self.current_cycle_data['findings'] = findings
            self.logger.info(f"Found {len(findings)} issues")

    def record_task(self, task_name: str, success: bool, details: Dict[str, Any] = None):
        """Record executed task"""
        if self.current_cycle_data:
            if success:
                self.current_cycle_data['tasks_executed'].append({
                    'task': task_name,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'details': details or {}
                })
            else:
                self.current_cycle_data['failures'].append({
                    'task': task_name,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'details': details or {}
                })

    def record_error(self, error_msg: str):
        """Record cycle error"""
        if self.current_cycle_data:
            self.current_cycle_data['error'] = error_msg
            self.logger.error(f"Cycle error: {error_msg}")

    def end_cycle(self) -> Dict[str, Any]:
        """End cycle and generate report"""
        if not self.current_cycle_data:
            return {}

        self.current_cycle_data['end_time'] = datetime.now(timezone.utc).isoformat()
        self.current_cycle_data['statistics'] = self._calculate_statistics(self.current_cycle_data)

        cycle_num = self.current_cycle_data['cycle']
        self.cycles.append(self.current_cycle_data)

        # Persist cycle data
        cycle_file = self.record_dir / f"cycle_{cycle_num}.json"
        with open(cycle_file, 'w') as f:
            json.dump(self.current_cycle_data, f, indent=2)

        report = self.generate_cycle_report(self.current_cycle_data)
        self.logger.info(f"Cycle {cycle_num} completed: {report['success_rate']} success rate")

        self.current_cycle_data = None
        return report

    def _calculate_statistics(self, cycle_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate cycle statistics"""
        tasks_executed = cycle_data.get('tasks_executed', [])
        failures = cycle_data.get('failures', [])
        total_tasks = len(tasks_executed) + len(failures)

        successful = len(tasks_executed)
        success_rate = (successful / total_tasks * 100) if total_tasks > 0 else 0

        return {
            'total_findings': len(cycle_data.get('findings', [])),
            'tasks_executed': len(tasks_executed),
            'tasks_failed': len(failures),
            'total_tasks': total_tasks,
            'success_rate': f"{success_rate:.1f}%",
            'success_rate_pct': success_rate
        }

    def generate_cycle_report(self, cycle_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive cycle report"""
        stats = cycle_data.get('statistics', {})
        return {
            'cycle': cycle_data['cycle'],
            'timestamp': cycle_data.get('start_time'),
            'findings': {
                'total': len(cycle_data.get('findings', [])),
                'by_type': self._categorize_findings(cycle_data.get('findings', [])),
            },
            'repairs': {
                'attempted': stats.get('total_tasks', 0),
                'successful': stats.get('tasks_executed', 0),
                'failed': stats.get('tasks_failed', 0)
            },
            'success_rate': stats.get('success_rate', '0%'),
            'errors': cycle_data.get('error')
        }

    def _categorize_findings(self, findings: List[Dict[str, Any]]) -> Dict[str, int]:
        """Categorize findings by type"""
        categories = {}
        for finding in findings:
            ftype = finding.get('type', 'unknown')
            categories[ftype] = categories.get(ftype, 0) + 1
        return categories

    def format_summary(self, cycle_limit: int = None) -> str:
        """Format metrics summary for display"""
        if not self.cycles:
            return "No cycles completed yet"

        cycles_to_report = self.cycles[-cycle_limit:] if cycle_limit else self.cycles

        total_findings = sum(len(c.get('findings', [])) for c in cycles_to_report)
        total_repairs = sum(len(c.get('tasks_executed', [])) for c in cycles_to_report)
        total_failures = sum(len(c.get('failures', [])) for c in cycles_to_report)

        if len(cycles_to_report) > 0:
            last_success_rate = cycles_to_report[-1].get('statistics', {}).get('success_rate', '0%')
        else:
            last_success_rate = '0%'

        return f"""
Unified Metrics Summary:
  • Cycles: {len(cycles_to_report)}
  • Findings: {total_findings}
  • Repairs: {total_repairs}
  • Failures: {total_failures}
  • Last success rate: {last_success_rate}
"""

    def get_cycle_metrics(self, cycle_num: int) -> Dict[str, Any]:
        """Retrieve metrics for specific cycle"""
        for cycle in self.cycles:
            if cycle['cycle'] == cycle_num:
                return cycle
        return {}

    def run_continuous(self, max_cycles: int = None, controller_fn=None):
        """Run continuous monitoring loop"""
        cycle = 0

        self.logger.info("Unified metrics monitoring started")

        while max_cycles is None or cycle < max_cycles:
            cycle += 1
            self.start_cycle(cycle)

            try:
                if controller_fn:
                    results = controller_fn()
                else:
                    results = {'findings': [], 'tasks_executed': [], 'failures': []}

                if results.get('findings'):
                    self.record_findings(results['findings'])
                if results.get('tasks_executed'):
                    for task in results['tasks_executed']:
                        self.record_task(task.get('name', 'unknown'), True, task)
                if results.get('failures'):
                    for failure in results['failures']:
                        self.record_task(failure.get('name', 'unknown'), False, failure)

                report = self.end_cycle()

            except Exception as e:
                self.record_error(str(e))
                self.end_cycle()

            if max_cycles is None or cycle < max_cycles:
                self.logger.info(f"Next cycle in {self.interval}s...")
                time.sleep(self.interval)

        self.logger.info(f"Monitoring completed {cycle} cycles")
        return cycle

    def export_metrics(self, format: str = 'json') -> str:
        """Export all metrics"""
        if format == 'json':
            return json.dumps([
                {
                    'cycle': c['cycle'],
                    'start_time': c['start_time'],
                    'end_time': c.get('end_time'),
                    'statistics': c.get('statistics', {})
                }
                for c in self.cycles
            ], indent=2)
        return str(self.cycles)

    def get_all_records(self) -> List[Dict[str, Any]]:
        """Get all recorded cycles"""
        records = []
        for cycle_file in sorted(self.record_dir.glob("cycle_*.json")):
            with open(cycle_file) as f:
                records.append(json.load(f))
        return records
