"""Autonomous Result Recording: Document everything"""
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timezone

class AutonomousRecorder:
    """Record all Studio activities and results"""

    def __init__(self, record_dir: str = '.studio_records'):
        self.record_dir = Path(record_dir)
        self.record_dir.mkdir(exist_ok=True)
        self.current_session = None

    def start_session(self) -> str:
        """Begin recording session"""
        self.current_session = {
            'session_id': f"session_{datetime.now(timezone.utc).isoformat()}",
            'start_time': datetime.now(timezone.utc).isoformat(),
            'activities': [],
            'decisions': [],
            'results': [],
            'errors': []
        }
        return self.current_session['session_id']

    def record_activity(self, activity_type: str, details: Dict[str, Any]):
        """Record any activity"""
        record = {
            'type': activity_type,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'details': details
        }
        if self.current_session:
            self.current_session['activities'].append(record)

    def record_decision(self, decision: Dict[str, Any]):
        """Record strategic decision"""
        record = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'decision': decision
        }
        if self.current_session:
            self.current_session['decisions'].append(record)

    def record_result(self, result_type: str, result: Dict[str, Any], success: bool):
        """Record operation result"""
        record = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'type': result_type,
            'success': success,
            'data': result
        }
        if self.current_session:
            self.current_session['results'].append(record)

    def record_error(self, error_type: str, error_message: str, traceback: str = None):
        """Record error"""
        record = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'type': error_type,
            'message': error_message,
            'traceback': traceback
        }
        if self.current_session:
            self.current_session['errors'].append(record)

    def end_session(self) -> str:
        """End session and save"""
        if not self.current_session:
            return None

        self.current_session['end_time'] = datetime.now(timezone.utc).isoformat()
        self.current_session['statistics'] = self._calculate_statistics()

        session_file = self.record_dir / f"{self.current_session['session_id']}.json"
        with open(session_file, 'w') as f:
            json.dump(self.current_session, f, indent=2)

        session_id = self.current_session['session_id']
        self.current_session = None
        return session_id

    def _calculate_statistics(self) -> Dict[str, Any]:
        """Calculate session stats"""
        if not self.current_session:
            return {}

        activities = self.current_session['activities']
        results = self.current_session['results']
        errors = self.current_session['errors']

        successful_results = sum(1 for r in results if r['success'])

        return {
            'total_activities': len(activities),
            'total_decisions': len(self.current_session['decisions']),
            'total_results': len(results),
            'successful_results': successful_results,
            'success_rate': successful_results / len(results) if results else 0,
            'total_errors': len(errors),
            'activity_breakdown': self._breakdown_activities(activities)
        }

    def _breakdown_activities(self, activities: List[Dict]) -> Dict[str, int]:
        """Count activities by type"""
        breakdown = {}
        for activity in activities:
            activity_type = activity.get('type', 'unknown')
            breakdown[activity_type] = breakdown.get(activity_type, 0) + 1
        return breakdown

    def generate_session_report(self, session_id: str = None) -> Dict[str, Any]:
        """Generate comprehensive session report"""
        if session_id is None and self.current_session:
            session_id = self.current_session['session_id']

        session_file = self.record_dir / f"{session_id}.json"
        if not session_file.exists():
            return {}

        with open(session_file) as f:
            session = json.load(f)

        return {
            'session_id': session['session_id'],
            'duration': f"From {session['start_time']} to {session['end_time']}",
            'summary': {
                'activities': session['statistics']['total_activities'],
                'decisions': session['statistics']['total_decisions'],
                'success_rate': f"{session['statistics']['success_rate']:.1%}",
                'errors': session['statistics']['total_errors']
            },
            'breakdown': session['statistics']['activity_breakdown']
        }

    def get_all_records(self) -> List[Dict[str, Any]]:
        """Get all recorded sessions"""
        records = []
        for session_file in sorted(self.record_dir.glob("*.json"), reverse=True):
            with open(session_file) as f:
                records.append(json.load(f))
        return records
