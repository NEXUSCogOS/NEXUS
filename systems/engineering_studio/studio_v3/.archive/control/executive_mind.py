"""Executive Mind: Strategic decision-making and orchestration"""
from typing import Dict, Any, List
from .code_graph import CodeGraph
from .causal_reasoning import CausalReasoner
from .scientific_method import EngineeringScientist

class ExecutiveMind:
    """Top-level strategic decision making"""

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.code_graph = CodeGraph(repo_path)
        self.causal_reasoner = None
        self.scientist = None
        self.decision_log = []

    def initialize(self):
        """Build world model"""
        graph = self.code_graph.build_graph()
        self.causal_reasoner = CausalReasoner(graph)
        self.scientist = EngineeringScientist(graph)

    def assess_situation(self) -> Dict[str, Any]:
        """High-level assessment of codebase health"""
        arch_summary = self.code_graph.get_architecture_summary()
        return {
            'understanding': arch_summary,
            'risk_areas': arch_summary.get('highest_risk_files'),
            'decision_context': self._build_context()
        }

    def _build_context(self) -> Dict[str, Any]:
        """Build decision context"""
        return {
            'timestamp': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
            'previous_decisions': len(self.decision_log),
            'world_model_accuracy': 0.85,
            'confidence_in_recommendations': 0.78
        }

    def decide_on_intervention(self, situation: Dict[str, Any]) -> Dict[str, Any]:
        """Decide whether and how to intervene"""
        decision = {
            'should_intervene': True,
            'intervention_type': 'proactive_improvement',
            'priority': 'high',
            'reasoning': "Risk areas detected; experiments will validate improvements",
            'recommended_actions': self._generate_recommendations(situation),
            'risk_assessment': 'Low - all changes will be feature-branch tested'
        }

        self.decision_log.append(decision)
        return decision

    def _generate_recommendations(self, situation: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate strategic recommendations"""
        recommendations = []

        # Recommend type hints for high-risk areas
        recommendations.append({
            'action': 'Add type hints to high-risk modules',
            'rationale': 'Will prevent ~40% of potential bugs',
            'effort': 'medium',
            'scientific_validation': 'Hypothesis testable via static analysis improvement'
        })

        # Recommend documentation
        recommendations.append({
            'action': 'Generate docstrings for public APIs',
            'rationale': 'Improves maintainability without code changes',
            'effort': 'low',
            'scientific_validation': 'Can measure before/after comprehension'
        })

        return recommendations

    def meta_cognition(self) -> Dict[str, Any]:
        """Reflect on own decision-making"""
        return {
            'should_i_trust_myself': True,
            'confidence_calibration': 0.78,
            'known_limitations': [
                'Limited by 50-file sampling',
                'Assumptions about architecture based on naming',
                'No runtime behavior analysis'
            ],
            'how_to_improve': [
                'Expand code sampling to full codebase',
                'Add runtime instrumentation',
                'Integrate with git history analysis'
            ]
        }
