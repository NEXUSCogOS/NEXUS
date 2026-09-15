"""Unified event recording for decisions, outcomes, and technical analysis"""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class EventRecorder:
    """Record all events, decisions, outcomes, and technical analysis"""

    def __init__(self, record_dir: str = '.studio_events'):
        self.record_dir = Path(record_dir)
        self.record_dir.mkdir(exist_ok=True)
        self.current_session = None
        self.events = []

    # Session management
    def start_session(self) -> str:
        """Begin recording session"""
        self.current_session = {
            'session_id': f"session_{datetime.now(timezone.utc).isoformat()}",
            'start_time': datetime.now(timezone.utc).isoformat(),
            'activities': [],
            'decisions': [],
            'results': [],
            'errors': [],
            'technical_papers': []
        }
        return self.current_session['session_id']

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

    # Activity recording
    def record_activity(self, activity_type: str, details: Dict[str, Any]):
        """Record any activity"""
        record = {
            'type': activity_type,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'details': details
        }
        if self.current_session:
            self.current_session['activities'].append(record)
        self.events.append(record)

    # Decision recording
    def record_decision(self, decision: Dict[str, Any]):
        """Record strategic decision"""
        record = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'decision': decision
        }
        if self.current_session:
            self.current_session['decisions'].append(record)
        self.events.append(record)

    def record_decision_paper(self, decision_id: str, decision_data: Dict[str, Any],
                             manifest_evaluation: Dict[str, Any],
                             experimental_results: Dict[str, Any]) -> str:
        """
        Record a complete decision as technical paper:
        - Decision rationale
        - Manifest alignment
        - Pros/cons weighting
        - Experimental outcomes
        - Lessons learned
        - Procedural recommendations
        """
        paper = {
            'paper_id': f"paper_{decision_id}_{datetime.now(timezone.utc).isoformat()}",
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'decision_id': decision_id,
            'metadata': {
                'title': f"Decision Analysis: {decision_data.get('type', 'unknown')}",
                'abstract': self._generate_abstract(decision_data),
                'keywords': self._extract_keywords(decision_data)
            },
            'sections': {
                'introduction': self._section_introduction(decision_data),
                'manifest_alignment': manifest_evaluation,
                'experimental_validation': experimental_results,
                'pros_cons_analysis': self._section_pros_cons(decision_data),
                'decision_rationale': self._section_decision(decision_data),
                'outcomes': {},
                'lessons_learned': {},
                'procedural_recommendations': self._section_recommendations(decision_data)
            }
        }

        self.events.append(paper)
        if self.current_session:
            self.current_session['technical_papers'].append(paper)

        self._persist_paper(paper)
        return paper['paper_id']

    def record_outcome(self, paper_id: str, outcome_data: Dict[str, Any]):
        """Record decision outcome and update paper"""
        for paper in self.events:
            if isinstance(paper, dict) and paper.get('paper_id') == paper_id:
                paper['sections']['outcomes'] = {
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'actual_metrics': outcome_data.get('actual_metrics', {}),
                    'vs_projected': outcome_data.get('vs_projected', {}),
                    'side_effects': outcome_data.get('side_effects', []),
                    'success': outcome_data.get('success', False)
                }

                # Generate lessons learned
                paper['sections']['lessons_learned'] = self._extract_lessons(
                    paper['sections']['experimental_validation'],
                    paper['sections']['outcomes']
                )

                self._persist_paper(paper)
                return paper_id

        return None

    # Result recording
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
        self.events.append(record)

    # Error recording
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
        self.events.append(record)

    # Statistics and reporting
    def _calculate_statistics(self) -> Dict[str, Any]:
        """Calculate session stats"""
        if not self.current_session:
            return {}

        activities = self.current_session.get('activities', [])
        results = self.current_session.get('results', [])
        errors = self.current_session.get('errors', [])

        successful_results = sum(1 for r in results if r.get('success'))

        return {
            'total_activities': len(activities),
            'total_decisions': len(self.current_session.get('decisions', [])),
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
            'duration': f"From {session['start_time']} to {session.get('end_time', 'ongoing')}",
            'summary': {
                'activities': session.get('statistics', {}).get('total_activities', 0),
                'decisions': session.get('statistics', {}).get('total_decisions', 0),
                'success_rate': f"{session.get('statistics', {}).get('success_rate', 0):.1%}",
                'errors': session.get('statistics', {}).get('total_errors', 0)
            },
            'breakdown': session.get('statistics', {}).get('activity_breakdown', {})
        }

    # Technical paper support
    def _generate_abstract(self, decision_data: Dict[str, Any]) -> str:
        """Generate paper abstract"""
        return f"This paper analyzes the decision to implement {decision_data.get('type', 'unknown')} repair. " \
               f"The decision was evaluated against optimal structure manifest, " \
               f"validated through controlled experimentation, " \
               f"and measured against frontier research benchmarks."

    def _extract_keywords(self, decision_data: Dict[str, Any]) -> List[str]:
        """Extract keywords from decision"""
        return [
            decision_data.get('type', 'repair'),
            'manifest-alignment',
            'controlled-experiment',
            'frontier-comparison',
            'decision-analysis'
        ]

    def _section_introduction(self, decision_data: Dict[str, Any]) -> Dict[str, Any]:
        """Write introduction section"""
        return {
            'problem_statement': f"Proposed repair: {decision_data.get('description', 'unknown')}",
            'motivation': decision_data.get('motivation', ''),
            'research_context': 'Compared against ICSE/FSE/ASE frontier research benchmarks',
            'objectives': [
                'Evaluate decision against optimal structure manifest',
                'Validate through controlled experimentation',
                'Measure pros/cons weighting',
                'Record outcomes for procedural enhancement'
            ]
        }

    def _section_pros_cons(self, decision_data: Dict[str, Any]) -> Dict[str, Any]:
        """Structured pros/cons analysis"""
        pros = decision_data.get('advantages', [])
        cons = decision_data.get('disadvantages', [])

        return {
            'pros': [{'pro': p, 'weight': 1.0} for p in pros],
            'cons': [{'con': c, 'weight': 1.0} for c in cons],
            'net_assessment': decision_data.get('net_score', 0),
            'efficiency_ratio': decision_data.get('efficiency', 0)
        }

    def _section_decision(self, decision_data: Dict[str, Any]) -> Dict[str, Any]:
        """Decision rationale section"""
        return {
            'decision': decision_data.get('decision', 'PENDING'),
            'rationale': [
                f"Manifest alignment: {decision_data.get('manifest_alignment', 'unknown')}",
                f"Statistical significance: {decision_data.get('significance', 'unknown')}",
                f"Effort efficiency: {decision_data.get('efficiency', 'unknown')}",
                f"Frontier comparison: {decision_data.get('frontier_comparison', 'unknown')}"
            ],
            'approval_basis': 'Manifest-driven + statistically validated + frontier-benchmarked'
        }

    def _section_recommendations(self, decision_data: Dict[str, Any]) -> Dict[str, Any]:
        """Procedural recommendations for future decisions"""
        return {
            'immediate_actions': decision_data.get('immediate_actions', []),
            'future_improvements': decision_data.get('improvement_suggestions', []),
            'pattern_for_similar_decisions': f"Apply this approach to all {decision_data.get('type', 'unknown')}-class repairs",
            'validation_template': 'Manifest alignment + controlled experiment + frontier comparison'
        }

    def _extract_lessons(self, experimental: Dict[str, Any],
                        outcomes: Dict[str, Any]) -> Dict[str, Any]:
        """Extract lessons from outcomes vs predictions"""
        return {
            'hypothesis_validity': 'Confirmed' if outcomes.get('success') else 'Rejected',
            'predicted_vs_actual': outcomes.get('vs_projected', {}),
            'unexpected_findings': outcomes.get('side_effects', []),
            'improvements_to_approach': [
                'Better side-effect prediction needed',
                'Increase experimentation sample size',
                'Cross-validate with additional frontier studies'
            ]
        }

    def _persist_paper(self, paper: Dict[str, Any]):
        """Save technical paper to disk"""
        paper_file = self.record_dir / f"{paper['paper_id']}.json"
        with open(paper_file, 'w') as f:
            json.dump(paper, f, indent=2)

    def generate_papers_index(self) -> Dict[str, Any]:
        """Generate searchable index of all papers"""
        papers = [e for e in self.events if isinstance(e, dict) and 'paper_id' in e]

        index = {
            'total_papers': len(papers),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'papers': [
                {
                    'id': p['paper_id'],
                    'title': p['metadata'].get('title'),
                    'decision_type': p.get('metadata', {}).get('decision_type'),
                    'timestamp': p['timestamp'],
                    'outcome_recorded': bool(p['sections'].get('outcomes'))
                }
                for p in papers
            ]
        }

        # Save index
        index_file = self.record_dir / 'index.json'
        with open(index_file, 'w') as f:
            json.dump(index, f, indent=2)

        return index

    def get_papers_by_capability(self, capability: str) -> List[Dict[str, Any]]:
        """Retrieve all papers for a capability"""
        papers = [e for e in self.events if isinstance(e, dict) and 'paper_id' in e]
        return [
            p for p in papers
            if p.get('metadata', {}).get('capability_affected') == capability
        ]

    def get_procedural_recommendations(self) -> List[Dict[str, Any]]:
        """Extract all procedural recommendations across papers"""
        recommendations = []
        papers = [e for e in self.events if isinstance(e, dict) and 'paper_id' in e]

        for paper in papers:
            section = paper['sections'].get('procedural_recommendations', {})
            recommendations.extend(
                section.get('future_improvements', [])
            )

        return recommendations

    def get_all_records(self) -> List[Dict[str, Any]]:
        """Get all recorded events"""
        records = []
        for event_file in sorted(self.record_dir.glob("session_*.json"), reverse=True):
            with open(event_file) as f:
                records.append(json.load(f))
        return records
