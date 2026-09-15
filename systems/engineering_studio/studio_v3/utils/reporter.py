"""Generate reports and summaries"""
from typing import Dict, Any, List
from datetime import datetime, timezone
import json

class ReportGenerator:
    """Generate cycle reports and summaries"""
    
    @staticmethod
    def create_cycle_report(cycle_num: int, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive cycle report"""
        return {
            'cycle': cycle_num,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'findings': {
                'total': len(results.get('findings', [])),
                'by_type': {},
                'by_severity': {}
            },
            'repairs': {
                'attempted': len(results.get('tasks_executed', [])) + len(results.get('failures', [])),
                'successful': len(results.get('tasks_executed', [])),
                'failed': len(results.get('failures', []))
            },
            'success_rate': ReportGenerator._calc_success_rate(results),
            'errors': results.get('error')
        }
    
    @staticmethod
    def _calc_success_rate(results: Dict[str, Any]) -> str:
        total = len(results.get('tasks_executed', [])) + len(results.get('failures', []))
        if total == 0:
            return "0%"
        rate = len(results.get('tasks_executed', [])) / total * 100
        return f"{rate:.1f}%"
    
    @staticmethod
    def format_summary(reports: List[Dict[str, Any]]) -> str:
        """Format summary for display"""
        if not reports:
            return "No cycles completed yet"
        
        total_findings = sum(r['findings']['total'] for r in reports)
        total_repairs = sum(r['repairs']['successful'] for r in reports)
        
        return f"""
Studio Performance Summary:
  • Cycles: {len(reports)}
  • Findings: {total_findings}
  • Repairs: {total_repairs}
  • Success rate: {reports[-1]['success_rate']}
"""
