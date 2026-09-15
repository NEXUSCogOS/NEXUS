"""Optimal structure manifest: Measure all decisions against ideal state"""
import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime, timezone

class OptimalStructureManifest:
    """Authoritative manifest of optimal system structure"""

    # Elite engineering reference architecture
    OPTIMAL_STRUCTURE = {
        'autonomous_repair': {
            'detection_accuracy': 0.96,
            'repair_success_rate': 0.88,
            'regression_rate': 0.01,
            'human_intervention_rate': 0.05,
            'methodology': 'ML-based + causal reasoning + scientific validation'
        },
        'code_understanding': {
            'architecture_understanding': 0.94,
            'dependency_mapping': 0.96,
            'purpose_inference': 0.90,
            'methodology': 'Graph neural networks + program analysis'
        },
        'causal_reasoning': {
            'root_cause_accuracy': 0.90,
            'prevention_strategy_relevance': 0.88,
            'counterfactual_validity': 0.85,
            'methodology': 'Causal graph inference + probabilistic reasoning'
        },
        'scientific_validation': {
            'hypothesis_validity': 0.95,
            'experiment_replicability': 0.92,
            'statistical_rigor': 0.90,
            'methodology': 'Pre-registration + Bayesian analysis'
        },
        'self_improvement': {
            'pattern_discovery_accuracy': 0.88,
            'self_improvement_rate_per_cycle': 0.20,  # 20% improvement per cycle
            'knowledge_retention': 0.95,
            'methodology': 'Meta-learning + reinforcement learning'
        }
    }

    def __init__(self):
        self.manifest = self.OPTIMAL_STRUCTURE
        self.manifest_dir = Path('.studio_manifest')
        self.manifest_dir.mkdir(exist_ok=True)

    def measure_against_manifest(self, capability: str,
                                current_metrics: Dict[str, float]) -> Dict[str, Any]:
        """Measure current state against optimal manifest"""
        if capability not in self.manifest:
            return {'error': f'No manifest entry for {capability}'}

        optimal = self.manifest[capability]
        measurement = {
            'capability': capability,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'current': current_metrics,
            'optimal': optimal,
            'gaps': {},
            'surpluses': {},
            'overall_health': 0
        }

        # Measure each metric
        total_gap = 0
        for metric, optimal_value in optimal.items():
            if metric == 'methodology':
                continue

            current_value = current_metrics.get(metric, 0)
            gap = optimal_value - current_value

            if gap > 0:
                measurement['gaps'][metric] = {
                    'current': current_value,
                    'optimal': optimal_value,
                    'gap': gap,
                    'gap_percentage': (gap / optimal_value * 100) if optimal_value > 0 else 0,
                    'priority': self._calculate_priority(gap, optimal_value)
                }
                total_gap += gap
            else:
                measurement['surpluses'][metric] = {
                    'current': current_value,
                    'optimal': optimal_value,
                    'surplus': abs(gap),
                    'status': 'exceeds_optimal'
                }

        # Calculate overall health
        metric_count = sum(1 for k, v in optimal.items() if k != 'methodology')
        measurement['overall_health'] = max(0, 100 - (total_gap / metric_count * 100)) if metric_count > 0 else 0

        return measurement

    def _calculate_priority(self, gap: float, optimal: float) -> str:
        """Prioritize gap closure"""
        gap_percentage = (gap / optimal * 100) if optimal > 0 else 0

        if gap_percentage > 20:
            return 'CRITICAL'
        elif gap_percentage > 10:
            return 'HIGH'
        elif gap_percentage > 5:
            return 'MEDIUM'
        else:
            return 'LOW'

    def evaluate_decision_against_manifest(self, decision: Dict[str, Any],
                                         affected_capability: str) -> Dict[str, Any]:
        """Evaluate a proposed decision against manifest requirements"""
        manifest_entry = self.manifest.get(affected_capability, {})

        evaluation = {
            'decision_id': decision.get('id'),
            'affected_capability': affected_capability,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'manifest_alignment': {},
            'weighted_assessment': {},
            'recommendation': None
        }

        # Check alignment with each manifest metric
        for metric, optimal_value in manifest_entry.items():
            if metric == 'methodology':
                continue

            projected_value = decision.get('projected_metrics', {}).get(metric, 0)
            contribution = projected_value - decision.get('current_metrics', {}).get(metric, 0)

            alignment = {
                'metric': metric,
                'current': decision.get('current_metrics', {}).get(metric, 0),
                'projected': projected_value,
                'optimal': optimal_value,
                'contribution': contribution,
                'moves_toward_optimal': contribution > 0,
                'remaining_gap': max(0, optimal_value - projected_value)
            }

            evaluation['manifest_alignment'][metric] = alignment

        # Weight advantages vs disadvantages
        evaluation['weighted_assessment'] = self._weight_decision(
            decision, evaluation['manifest_alignment'], manifest_entry
        )

        # Generate recommendation
        evaluation['recommendation'] = self._generate_recommendation(
            evaluation['weighted_assessment']
        )

        return evaluation

    def _weight_decision(self, decision: Dict[str, Any],
                        manifest_alignment: Dict[str, Any],
                        manifest: Dict[str, Any]) -> Dict[str, Any]:
        """Weight advantages vs disadvantages"""
        advantages = decision.get('advantages', [])
        disadvantages = decision.get('disadvantages', [])

        # Score advantages (each point toward manifest = +1)
        advantage_score = sum(
            alignment['contribution'] * 10  # Weight by contribution magnitude
            for alignment in manifest_alignment.values()
            if alignment.get('contribution', 0) > 0
        )

        # Score disadvantages (each point away = -1)
        disadvantage_score = sum(
            cost.get('impact', 0) * 10
            for cost in disadvantages
        )

        # Effort weighting (opportunity cost)
        effort_cost = decision.get('effort_hours', 0)

        return {
            'advantage_score': advantage_score,
            'disadvantage_score': disadvantage_score,
            'effort_cost_hours': effort_cost,
            'net_score': advantage_score - disadvantage_score,
            'efficiency': (advantage_score - disadvantage_score) / max(1, effort_cost),
            'recommendation_basis': 'Manifest alignment + weighted pros/cons + effort efficiency'
        }

    def _generate_recommendation(self, weighted_assessment: Dict[str, Any]) -> str:
        """Generate recommendation based on weighting"""
        net_score = weighted_assessment.get('net_score', 0)
        efficiency = weighted_assessment.get('efficiency', 0)

        if net_score > 8 and efficiency > 1:
            return 'STRONGLY RECOMMEND: High manifest alignment, strong efficiency'
        elif net_score > 5 and efficiency > 0.5:
            return 'RECOMMEND: Good manifest alignment, reasonable efficiency'
        elif net_score > 0:
            return 'CONDITIONAL: Marginal manifest alignment, consider optimization'
        else:
            return 'DO NOT RECOMMEND: Net disadvantage against manifest'

    def get_manifest(self) -> Dict[str, Any]:
        """Get current manifest"""
        return self.manifest

    def save_manifest(self):
        """Persist manifest to disk"""
        manifest_file = self.manifest_dir / 'optimal_structure_manifest.json'
        with open(manifest_file, 'w') as f:
            json.dump(self.manifest, f, indent=2)
