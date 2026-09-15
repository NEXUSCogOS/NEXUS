"""Integration layer - bring all components together"""
from .detectors import FindingDetector
from .scheduler import TaskScheduler
from .escalation import EscalationEngine
from .approval_queue import ApprovalQueue
from .notifications import NotificationSystem
from .metrics import MetricsCollector
from .learning import AdaptiveLearning
from .reporter import ReportGenerator
from typing import Dict, Any

class StudioIntegration:
    """Unified orchestration of all Studio components"""
    
    def __init__(self, config_path: str, repo_path: str):
        self.config_path = config_path
        self.repo_path = repo_path
        
        self.detector = FindingDetector(repo_path)
        self.scheduler = TaskScheduler()
        self.escalation = EscalationEngine()
        self.approvals = ApprovalQueue()
        self.notifications = NotificationSystem()
        self.metrics = MetricsCollector()
        self.learning = AdaptiveLearning()
    
    def run_full_cycle(self) -> Dict[str, Any]:
        """Run complete Studio cycle with all components"""
        results = {
            'findings': [],
            'scheduled': [],
            'escalated': [],
            'approved': [],
            'executed': []
        }
        
        # Detect all issues
        all_findings = self.detector.scan_all()
        for finding_type, findings in all_findings.items():
            results['findings'].extend(findings)
        
        # Schedule and evaluate each
        for finding in results['findings'][:10]:  # Limit to 10 per cycle
            escalation_eval = self.escalation.evaluate({'type': finding['type'], 'risk_level': finding.get('severity')})
            
            if escalation_eval['escalate']:
                self.approvals.add_to_queue(finding, f"Needs approval: {finding['type']}")
                results['escalated'].append(finding['finding_id'])
                self.notifications.notify_escalation(finding, escalation_eval['action'])
            else:
                task_id = self.scheduler.schedule_repair(finding)
                results['scheduled'].append(task_id)
        
        return results
