from typing import Dict, Any

class Prioritiser:
    # Pre-approved LOW-risk tasks (autonomous without human gate)
    PREAPPROVED_PATTERNS = {
        'missing_readme': {
            'risk_level': 'LOW',
            'auto_approve': True,
            'max_attempts': 3,
        }
    }

    def classify_finding(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify finding for risk and auto-approval
        Returns enriched finding with risk_level, auto_approve
        """
        finding_type = finding['type']

        if finding_type in self.PREAPPROVED_PATTERNS:
            pattern = self.PREAPPROVED_PATTERNS[finding_type]
            finding['risk_level'] = pattern['risk_level']
            finding['auto_approve'] = pattern['auto_approve']
            finding['max_attempts'] = pattern['max_attempts']
        else:
            finding['risk_level'] = 'UNKNOWN'
            finding['auto_approve'] = False
            finding['max_attempts'] = 0

        return finding
