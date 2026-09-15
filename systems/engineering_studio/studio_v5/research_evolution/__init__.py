"""
V5 Research Evolution Module - Canonical frontier research and self-improvement implementations

Exports:
- FrontierScanner: Scans for improvement opportunities
- ArchitectureComparator: Compares against frontier patterns
- FrontierResearchCorpus: Maintains frontier research benchmarks
- ResearchIntegrationOrchestrator: Orchestrates research-informed decisions
- EvolutionReporter: Reports evolution progress
- ExperimentRunner: Runs controlled experiments
- ValidationGate: Validates changes
- BenchmarkTracker: Tracks performance benchmarks
"""

# Bridge implementations from v3 (consolidated here as canonical)
from .frontier_research_corpus import FrontierResearchCorpus
from .research_integration_orchestrator import ResearchIntegrationOrchestrator

# Core research modules (with graceful fallbacks for incomplete implementations)
try:
    from .scanner.frontier_scanner import FrontierScanner, scan as frontier_scan
except ImportError:
    FrontierScanner = None
    frontier_scan = None

try:
    from .comparison.architecture_comparator import ArchitectureComparator, compare as compare_architecture
except ImportError:
    ArchitectureComparator = None
    compare_architecture = None

try:
    from .comparison.capability_gap_analyser import CapabilityGapAnalyser, analyze as analyze_gaps
except ImportError:
    CapabilityGapAnalyser = None
    analyze_gaps = None

try:
    from .reports.evolution_reporter import EvolutionReporter, report as generate_report
except ImportError:
    EvolutionReporter = None
    generate_report = None

try:
    from .experiments.experiment_runner import ExperimentRunner, run_experiment
except ImportError:
    ExperimentRunner = None
    run_experiment = None

try:
    from .validation.validation_gate import ValidationGate, validate as validate_finding
except ImportError:
    ValidationGate = None
    validate_finding = None

try:
    from .benchmarks.benchmark_tracker import BenchmarkTracker, record_benchmark
except ImportError:
    BenchmarkTracker = None
    record_benchmark = None

try:
    from .corpus.corpus_updater import CorpusUpdater, update as update_corpus
except ImportError:
    CorpusUpdater = None
    update_corpus = None

__all__ = [
    # Bridge implementations (v3 consolidation - always available)
    'FrontierResearchCorpus',
    'ResearchIntegrationOrchestrator',
    # Core research modules - Classes
    'FrontierScanner',
    'ArchitectureComparator',
    'CapabilityGapAnalyser',
    'EvolutionReporter',
    'ExperimentRunner',
    'ValidationGate',
    'BenchmarkTracker',
    'CorpusUpdater',
    # Core research modules - Functions
    'frontier_scan',
    'compare_architecture',
    'analyze_gaps',
    'generate_report',
    'run_experiment',
    'validate_finding',
    'record_benchmark',
    'update_corpus',
]
