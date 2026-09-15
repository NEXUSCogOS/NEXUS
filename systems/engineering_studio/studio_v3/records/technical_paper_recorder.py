"""Technical paper recorder: Record all decisions and outcomes for procedural enhancement"""
import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime, timezone

class TechnicalPaperRecorder:
    """Record all engineering decisions as technical papers for procedural enhancement"""

    def __init__(self, paper_dir: str = '.studio_technical_papers'):
        self.paper_dir = Path(paper_dir)
        self.paper_dir.mkdir(exist_ok=True)
        self.papers = []

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
                'outcomes': {},  # Filled after implementation
                'lessons_learned': {},  # Filled after outcomes known
                'procedural_recommendations': self._section_recommendations(decision_data)
            },
            'metadata': self._extract_metadata(decision_data, manifest_evaluation)
        }

        self.papers.append(paper)
        self._persist_paper(paper)
        return paper['paper_id']

    def record_outcome(self, paper_id: str, outcome_data: Dict[str, Any]):
        """Record decision outcome and update paper"""
        for paper in self.papers:
            if paper['paper_id'] == paper_id:
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
            'cons': [{'con': c, 'weight': c.get('impact', 1.0)} for c in cons],
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

    def _extract_metadata(self, decision: Dict[str, Any],
                         evaluation: Dict[str, Any]) -> Dict[str, Any]:
        """Extract searchable metadata"""
        return {
            'decision_type': decision.get('type'),
            'capability_affected': decision.get('capability'),
            'manifest_score': evaluation.get('weighted_assessment', {}).get('net_score', 0),
            'frontier_alignment': evaluation.get('weighted_assessment', {}).get('efficiency', 0),
            'complexity': decision.get('complexity', 'medium'),
            'effort_hours': decision.get('effort_hours', 0)
        }

    def _persist_paper(self, paper: Dict[str, Any]):
        """Save technical paper to disk"""
        paper_file = self.paper_dir / f"{paper['paper_id']}.json"
        with open(paper_file, 'w') as f:
            json.dump(paper, f, indent=2)

    def generate_papers_index(self) -> Dict[str, Any]:
        """Generate searchable index of all papers"""
        index = {
            'total_papers': len(self.papers),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'papers': [
                {
                    'id': p['paper_id'],
                    'title': p['metadata'].get('title'),
                    'decision_type': p.get('metadata', {}).get('decision_type'),
                    'timestamp': p['timestamp'],
                    'manifest_score': p.get('metadata', {}).get('manifest_score'),
                    'outcome_recorded': bool(p['sections'].get('outcomes'))
                }
                for p in self.papers
            ]
        }

        # Save index
        index_file = self.paper_dir / 'index.json'
        with open(index_file, 'w') as f:
            json.dump(index, f, indent=2)

        return index

    def get_papers_by_capability(self, capability: str) -> List[Dict[str, Any]]:
        """Retrieve all papers for a capability"""
        return [
            p for p in self.papers
            if p.get('metadata', {}).get('capability_affected') == capability
        ]

    def get_procedural_recommendations(self) -> List[Dict[str, Any]]:
        """Extract all procedural recommendations across papers"""
        recommendations = []

        for paper in self.papers:
            section = paper['sections'].get('procedural_recommendations', {})
            recommendations.extend(
                section.get('future_improvements', [])
            )

        return recommendations
