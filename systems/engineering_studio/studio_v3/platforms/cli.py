"""Enhanced CLI for Studio operations"""
import argparse
import sys
from pathlib import Path
from .dashboard import Dashboard
from .approval_queue import ApprovalQueue
from .metrics import MetricsCollector

class StudioCLI:
    """Studio command-line interface"""

    def __init__(self):
        self.dashboard = Dashboard()
        self.approvals = ApprovalQueue()
        self.metrics = MetricsCollector()

    def status(self):
        """Show system status"""
        print(self.dashboard.render_status())

    def approvals_list(self):
        """List pending approvals"""
        pending = self.approvals.get_pending()
        if not pending:
            print("✅ No pending approvals")
            return

        print("\n📋 PENDING APPROVALS:\n")
        for i, task in enumerate(pending, 1):
            print(f"{i}. {task['task_id']}")
            print(f"   Type: {task['task_type']}")
            print(f"   Risk: {task['risk_level']}")
            print(f"   Reason: {task['reason']}\n")

    def approve_task(self, task_id: str):
        """Approve a task"""
        self.approvals.approve(task_id)
        print(f"✅ Task {task_id} approved")

    def reject_task(self, task_id: str):
        """Reject a task"""
        self.approvals.reject(task_id)
        print(f"✅ Task {task_id} rejected")

    def health(self):
        """Show system health"""
        health = self.metrics.get_health_status()
        print("\n🏥 SYSTEM HEALTH:\n")
        for key, value in health.items():
            print(f"  {key}: {value}")

    def run(self, args=None):
        """Run CLI"""
        parser = argparse.ArgumentParser(description='Engineering Studio CLI')
        subparsers = parser.add_subparsers(dest='command')

        subparsers.add_parser('status', help='Show system status')
        subparsers.add_parser('health', help='Show system health')
        subparsers.add_parser('approvals', help='List pending approvals')

        approve = subparsers.add_parser('approve', help='Approve a task')
        approve.add_argument('task_id', help='Task ID to approve')

        reject = subparsers.add_parser('reject', help='Reject a task')
        reject.add_argument('task_id', help='Task ID to reject')

        parsed = parser.parse_args(args)

        if parsed.command == 'status':
            self.status()
        elif parsed.command == 'health':
            self.health()
        elif parsed.command == 'approvals':
            self.approvals_list()
        elif parsed.command == 'approve':
            self.approve_task(parsed.task_id)
        elif parsed.command == 'reject':
            self.reject_task(parsed.task_id)
        else:
            parser.print_help()

if __name__ == '__main__':
    cli = StudioCLI()
    cli.run()
