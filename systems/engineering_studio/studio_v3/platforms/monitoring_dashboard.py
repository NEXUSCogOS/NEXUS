"""
Real-time monitoring dashboard for concurrent project execution
Shows active projects, test execution progress, learning metrics, and resource monitoring
with frontier-level UI presentation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from dataclasses import asdict
import time
import sys

from ..execution.async_executor import (
    AsyncProjectExecutor, ProjectStatus, ExecutionMetrics
)


class ProgressBar:
    """Render a text-based progress bar"""

    @staticmethod
    def render(current: int, total: int, width: int = 30, label: str = "") -> str:
        """Render progress bar"""
        if total == 0:
            percentage = 0
        else:
            percentage = (current / total) * 100

        filled = int(width * current / total) if total > 0 else 0
        bar = "▓" * filled + "░" * (width - filled)
        return f"{label:<15} [{bar}] {percentage:>6.1f}% ({current}/{total})"


class MetricsFormatter:
    """Format metrics for display"""

    @staticmethod
    def format_duration(seconds: float) -> str:
        """Format duration in readable format"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds / 60:.1f}m"
        else:
            return f"{seconds / 3600:.1f}h"

    @staticmethod
    def format_throughput(projects_per_hour: float) -> str:
        """Format throughput"""
        if projects_per_hour == 0:
            return "0 proj/h"
        return f"{projects_per_hour:.1f} proj/h"

    @staticmethod
    def format_speedup(speedup: float) -> str:
        """Format speedup multiplier"""
        return f"{speedup:.1f}x faster"


class RealTimeDashboard:
    """Live status dashboard for concurrent project execution"""

    def __init__(self, executor: AsyncProjectExecutor, refresh_interval: float = 1.0):
        self.executor = executor
        self.refresh_interval = refresh_interval
        self._last_render_time = time.time()
        self._execution_history: List[Dict[str, Any]] = []

    def render_header(self) -> str:
        """Render dashboard header"""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    ENGINEERING STUDIO v3 - LIVE DASHBOARD                    ║
║                        Multi-Project Async Execution                         ║
║                                                                              ║
║  {timestamp:<74} ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

    def render_metrics_header(self) -> str:
        """Render metrics section header"""
        return """
📊 EXECUTION METRICS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    def render_metrics_summary(self, metrics: ExecutionMetrics) -> str:
        """Render core execution metrics"""
        output = self.render_metrics_header()

        # Main metrics row
        output += f"""
Status:    🟢 RUNNING ({metrics.completed} completed | {metrics.running} active | {metrics.queued} queued)
Speedup:   {MetricsFormatter.format_speedup(metrics.concurrent_speedup)}
Throughput: {MetricsFormatter.format_throughput(metrics.throughput_projects_per_hour)}

Progress:  {ProgressBar.render(
    metrics.completed + metrics.failed,
    metrics.total_projects,
    width=40,
    label="Total"
)}
"""

        return output

    def render_learning_metrics(self, metrics: ExecutionMetrics) -> str:
        """Render learning-related metrics"""
        output = """
🧠 LEARNING METRICS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        output += f"Patterns Learned:    {metrics.patterns_learned:>6} patterns\n"
        output += f"Lessons Extracted:   {metrics.lessons_extracted:>6} lessons\n"
        output += f"Avg Project Time:    {MetricsFormatter.format_duration(metrics.average_project_time)}\n"
        output += f"Total Time:          {MetricsFormatter.format_duration(metrics.total_execution_time)}\n"

        return output

    def render_project_status(self, executor: AsyncProjectExecutor) -> str:
        """Render individual project statuses"""
        output = """
🚀 ACTIVE PROJECTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""

        # Group projects by status
        running = []
        completed = []
        failed = []

        for execution in executor.executions.values():
            if execution.status == ProjectStatus.RUNNING:
                running.append(execution)
            elif execution.status == ProjectStatus.COMPLETED:
                completed.append(execution)
            elif execution.status == ProjectStatus.FAILED:
                failed.append(execution)

        # Display running projects
        if running:
            output += "▶ RUNNING:\n"
            for exec_item in running[:5]:  # Show top 5
                elapsed = (
                    (datetime.now(timezone.utc) - exec_item.started_at).total_seconds()
                    if exec_item.started_at else 0
                )
                output += f"  • {exec_item.project_name:<40} {MetricsFormatter.format_duration(elapsed)}\n"
            if len(running) > 5:
                output += f"  ... and {len(running) - 5} more\n"
            output += "\n"

        # Display completed projects
        if completed:
            output += f"✓ COMPLETED ({len(completed)}):\n"
            for exec_item in completed[-3:]:  # Show last 3
                output += f"  • {exec_item.project_name:<40} {MetricsFormatter.format_duration(exec_item.execution_time_seconds)}\n"
            if len(completed) > 3:
                output += f"  ... and {len(completed) - 3} more\n"
            output += "\n"

        # Display failed projects
        if failed:
            output += f"✗ FAILED ({len(failed)}):\n"
            for exec_item in failed:
                output += f"  • {exec_item.project_name:<40} {exec_item.error}\n"

        return output

    def render_resource_monitoring(self, executor: AsyncProjectExecutor) -> str:
        """Render resource monitoring info"""
        output = """
⚙️  RESOURCE MONITORING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""

        metrics = executor.metrics
        concurrency_usage = metrics.running / executor.max_concurrent
        queue_size = executor.queue.queue_size()
        queue_capacity = executor.queue.max_queue_size

        output += f"Concurrency:   {ProgressBar.render(metrics.running, executor.max_concurrent, width=20)}\n"
        output += f"Queue:         {ProgressBar.render(queue_size, queue_capacity, width=20)}\n"
        output += f"\nConcurrent Capacity: {metrics.running}/{executor.max_concurrent}\n"
        output += f"Queue Capacity:      {queue_size}/{queue_capacity}\n"

        return output

    async def render_live(self, executor: AsyncProjectExecutor, duration_seconds: Optional[int] = None) -> None:
        """
        Render live dashboard that updates in real-time

        Args:
            executor: AsyncProjectExecutor instance to monitor
            duration_seconds: Optional max duration to display
        """
        import asyncio

        start_time = time.time()
        try:
            while executor._running:
                # Clear screen
                print("\033[2J\033[H", end="")

                # Render dashboard
                dashboard_output = self.render_full_dashboard(executor)
                print(dashboard_output)

                # Check duration limit
                if duration_seconds:
                    elapsed = time.time() - start_time
                    if elapsed >= duration_seconds:
                        break

                # Wait for next refresh
                await asyncio.sleep(self.refresh_interval)

        except KeyboardInterrupt:
            print("\n\nDashboard closed by user")

    def render_full_dashboard(self, executor: AsyncProjectExecutor) -> str:
        """Render complete dashboard"""
        output = ""

        # Header
        output += self.render_header()

        # Metrics summary
        output += self.render_metrics_summary(executor.metrics)

        # Learning metrics
        output += self.render_learning_metrics(executor.metrics)

        # Project status
        output += self.render_project_status(executor)

        # Resource monitoring
        output += self.render_resource_monitoring(executor)

        # Footer with controls
        output += """
╔══════════════════════════════════════════════════════════════════════════════╗
║  Legend: ▓ = Completed  ░ = Pending                                         ║
║  Press Ctrl+C to close dashboard                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

        return output

    def render_summary_report(self, executor: AsyncProjectExecutor) -> str:
        """Render final summary report after execution"""
        metrics = executor.metrics

        output = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                      EXECUTION SUMMARY REPORT                               ║
╚══════════════════════════════════════════════════════════════════════════════╝

📈 RESULTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Projects:        {metrics.total_projects}
Completed:             {metrics.completed} ✓
Failed:                {metrics.failed} ✗
Success Rate:          {(metrics.completed / max(metrics.total_projects, 1)) * 100:.1f}%

⚡ PERFORMANCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Execution Time:  {MetricsFormatter.format_duration(metrics.total_execution_time)}
Average Project Time:  {MetricsFormatter.format_duration(metrics.average_project_time)}
Throughput:            {MetricsFormatter.format_throughput(metrics.throughput_projects_per_hour)}
Speedup Factor:        {MetricsFormatter.format_speedup(metrics.concurrent_speedup)}

🧠 LEARNING OUTCOMES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Patterns Learned:      {metrics.patterns_learned}
Lessons Extracted:     {metrics.lessons_extracted}
Learning Velocity:     {metrics.patterns_learned / max(metrics.total_execution_time / 3600, 0.001):.1f} patterns/hour

╔══════════════════════════════════════════════════════════════════════════════╗
║  Frontier-Level Performance Achieved: {metrics.concurrent_speedup:.1f}x speedup with {metrics.completed} concurrent projects ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

        return output

    def save_dashboard_state(self, executor: AsyncProjectExecutor, filepath: Optional[str] = None) -> None:
        """Save dashboard state to JSON file"""
        if not filepath:
            filepath = f".studio_dashboards/dashboard_{datetime.now(timezone.utc).isoformat()}.json"

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        state = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'metrics': asdict(executor.metrics),
            'executions': {
                project_id: {
                    'project_id': e.project_id,
                    'project_name': e.project_name,
                    'status': e.status.value,
                    'execution_time_seconds': e.execution_time_seconds,
                    'learning_metrics': (
                        asdict(e.learning_metrics) if e.learning_metrics else None
                    )
                }
                for project_id, e in executor.executions.items()
            }
        }

        Path(filepath).write_text(json.dumps(state, indent=2))


class ConsoleDashboard(RealTimeDashboard):
    """Console-based implementation of dashboard (suitable for CI/CD)"""

    def render_static(self, executor: AsyncProjectExecutor) -> str:
        """Render static dashboard for console output"""
        return self.render_full_dashboard(executor)

    def log_execution_milestone(self, message: str, icon: str = "→"):
        """Log execution milestone to console"""
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"[{timestamp}] {icon} {message}")
