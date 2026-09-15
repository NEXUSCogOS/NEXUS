"""
Research subsystem - BRIDGE LAYER to v5 canonical implementations

This module re-exports the canonical implementations from v5/research_evolution.
All research functionality is now consolidated in v5 for maintainability and isolation.

Backward compatibility: Existing code importing from studio_v3.research continues to work.
"""

import sys
from pathlib import Path

# Setup path to v5 modules
studio_root = Path(__file__).parent.parent.parent
studio_v5_path = studio_root / 'studio_v5'
if studio_v5_path.exists() and str(studio_root) not in sys.path:
    sys.path.insert(0, str(studio_root))

# Bridge imports from v5 canonical implementations
try:
    from systems.engineering_studio.studio_v5.research_evolution import (
        FrontierResearchCorpus,
        ResearchIntegrationOrchestrator,
        FrontierScanner,
        ArchitectureComparator,
        EvolutionReporter,
    )
except ImportError as e:
    # Fallback: provide minimal placeholder implementations
    import warnings
    warnings.warn(
        f"Could not import v5 research_evolution: {e}. "
        "Providing placeholder implementations. "
        "Ensure studio_v5/research_evolution is properly installed."
    )

    class FrontierResearchCorpus:
        """Fallback placeholder for FrontierResearchCorpus."""
        def __init__(self):
            self.FRONTIER_BENCHMARKS = {}

        def get_all_frontiers(self):
            return self.FRONTIER_BENCHMARKS

        def compare_to_frontier(self, **kwargs):
            return {'error': 'FrontierResearchCorpus not properly initialized'}

    class ResearchIntegrationOrchestrator:
        """Fallback placeholder for ResearchIntegrationOrchestrator."""
        pass

    class FrontierScanner:
        """Placeholder for FrontierScanner."""
        pass

    class ArchitectureComparator:
        """Placeholder for ArchitectureComparator."""
        pass

    class EvolutionReporter:
        """Placeholder for EvolutionReporter."""
        pass

__all__ = [
    'FrontierResearchCorpus',
    'ResearchIntegrationOrchestrator',
    'FrontierScanner',
    'ArchitectureComparator',
    'EvolutionReporter',
]
