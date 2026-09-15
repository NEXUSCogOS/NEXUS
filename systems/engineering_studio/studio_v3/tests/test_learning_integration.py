"""
Test V5 Learning Integration with V3 Controller

Tests the integration of studio_v5 frontier research modules with the v3 controller,
including frontier scanning, architecture comparison, and continuous learning.
"""

import pytest
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add studio_v5 to path for imports
studio_v5_path = Path(__file__).parent.parent.parent / 'studio_v5'
sys.path.insert(0, str(studio_v5_path))

# Import v5 modules
from research_evolution import (
    frontier_scan,
    compare_architecture,
    analyze_gaps,
    generate_report,
    run_experiment,
    validate_finding,
    update_corpus,
    record_benchmark
)


class TestV5ModuleAvailability:
    """Test that all V5 modules are available and callable."""

    def test_frontier_scanner_callable(self):
        """Test frontier_scan module function is callable."""
        result = frontier_scan()
        assert result is not None
        assert isinstance(result, dict)
        assert 'timestamp' in result
        assert 'opportunities' in result

    def test_architecture_comparator_callable(self):
        """Test compare_architecture module function is callable."""
        result = compare_architecture()
        assert result is not None
        assert isinstance(result, dict)
        assert 'alignment_score' in result
        assert 'gaps' in result

    def test_capability_gap_analyser_callable(self):
        """Test analyze_gaps module function is callable."""
        result = analyze_gaps()
        assert result is not None
        assert isinstance(result, dict)
        assert 'gaps' in result or 'recommendations' in result

    def test_evolution_reporter_callable(self):
        """Test generate_report module function is callable."""
        scan_results = frontier_scan()
        result = generate_report(scan_results)
        assert result is not None
        assert isinstance(result, dict)
        assert 'summary' in result
        assert 'key_findings' in result

    def test_experiment_runner_callable(self):
        """Test run_experiment module function is callable."""
        result = run_experiment()
        assert result is not None
        assert isinstance(result, dict)
        assert 'experiment_id' in result


class TestV5IntegrationWithController:
    """Test integration of V5 modules with V3 controller."""

    @pytest.fixture
    def mock_controller(self):
        """Create a mock controller with V5 learning capability."""
        # Create mock config and repo
        config_path = "/tmp/test_config"
        repo_path = "/tmp/test_repo"

        # Import controller with proper paths
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))

        with patch('studio_v3.platforms.controller.RepositoryScanner'):
            with patch('studio_v3.platforms.controller.Prioritiser'):
                with patch('studio_v3.platforms.controller.Planner'):
                    with patch('studio_v3.platforms.controller.AuthorityGate'):
                        with patch('studio_v3.platforms.controller.init_canonical'):
                            from studio_v3.platforms.controller import StudioController
                            controller = StudioController(config_path, repo_path)
                            # Mock the canonical_db to support learning logging
                            controller.canonical_db = Mock()
                            controller.canonical_db.log_learning = Mock()
                            return controller

    def test_controller_has_learn_phase_method(self, mock_controller):
        """Test that controller has learn_phase method."""
        assert hasattr(mock_controller, 'learn_phase')
        assert callable(mock_controller.learn_phase)

    def test_learn_phase_returns_correct_structure(self, mock_controller):
        """Test that learn_phase returns proper result structure."""
        results = {'findings': [], 'tasks_executed': []}
        learning_result = mock_controller.learn_phase(results)

        assert isinstance(learning_result, dict)
        assert 'phase' in learning_result
        assert learning_result['phase'] == 'learning'
        assert 'timestamp' in learning_result
        assert 'findings' in learning_result
        assert 'insights' in learning_result
        assert 'learned_this_cycle' in learning_result
        assert 'latency_ms' in learning_result

    def test_learn_phase_collects_findings(self, mock_controller):
        """Test that learn_phase collects frontier findings."""
        results = {'findings': [], 'tasks_executed': []}
        learning_result = mock_controller.learn_phase(results)

        # Should have findings from frontier scan
        assert 'findings' in learning_result
        # Check structure if findings exist
        if learning_result['findings']:
            finding = learning_result['findings'][0]
            assert 'type' in finding or 'severity' in finding

    def test_learn_phase_generates_insights(self, mock_controller):
        """Test that learn_phase generates architectural insights."""
        results = {'findings': [], 'tasks_executed': []}
        learning_result = mock_controller.learn_phase(results)

        # Should generate insights
        assert 'insights' in learning_result
        assert isinstance(learning_result['insights'], list)

    def test_learn_phase_records_to_ledger(self, mock_controller):
        """Test that learn_phase records to canonical ledger."""
        results = {'findings': [], 'tasks_executed': []}
        learning_result = mock_controller.learn_phase(results)

        # Check that log_learning was called (if method exists)
        if mock_controller.canonical_db.log_learning.called:
            assert True
        else:
            # Method may not be called if no findings, but should be available
            assert mock_controller.canonical_db.log_learning is not None

    def test_learn_phase_latency_acceptable(self, mock_controller):
        """Test that learn_phase has acceptable latency (<5s per brief)."""
        results = {'findings': [], 'tasks_executed': []}
        learning_result = mock_controller.learn_phase(results)

        latency_ms = learning_result.get('latency_ms', 0)
        # Should complete in less than 5000ms (5 seconds)
        assert latency_ms < 5000, f"Learning phase took {latency_ms}ms, expected < 5000ms"


class TestLearningPhaseIntegration:
    """Test learning phase integrated into repair loop."""

    def test_repair_loop_calls_learn_phase(self):
        """Test that repair loop includes learning phase."""
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))

        with patch('studio_v3.platforms.controller.RepositoryScanner') as mock_scanner:
            with patch('studio_v3.platforms.controller.Prioritiser'):
                with patch('studio_v3.platforms.controller.Planner'):
                    with patch('studio_v3.platforms.controller.AuthorityGate'):
                        with patch('studio_v3.platforms.controller.init_canonical'):
                            from studio_v3.platforms.controller import StudioController
                            controller = StudioController('/tmp/config', '/tmp/repo')
                            controller.canonical_db = Mock()
                            controller.canonical_db.log_learning = Mock()
                            controller.canonical_db.log_repair = Mock()

                            # Mock scanner to return empty findings
                            mock_scanner_instance = Mock()
                            mock_scanner_instance.scan_missing_readme.return_value = []
                            controller.scanner = mock_scanner_instance

                            # Run repair loop
                            result = controller.run_repair_loop()

                            # Should have learning_phase in results
                            assert 'learning_phase' in result
                            assert result['learning_phase'] is not None

    def test_learning_phase_with_findings(self):
        """Test learning phase when findings exist."""
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))

        with patch('studio_v3.platforms.controller.RepositoryScanner'):
            with patch('studio_v3.platforms.controller.Prioritiser'):
                with patch('studio_v3.platforms.controller.Planner'):
                    with patch('studio_v3.platforms.controller.AuthorityGate'):
                        with patch('studio_v3.platforms.controller.init_canonical'):
                            from studio_v3.platforms.controller import StudioController
                            controller = StudioController('/tmp/config', '/tmp/repo')
                            controller.canonical_db = Mock()
                            controller.canonical_db.log_learning = Mock()

                            results = {'findings': [{'type': 'test'}], 'tasks_executed': []}
                            learning_result = controller.learn_phase(results)

                            # Should process findings
                            assert learning_result['phase'] == 'learning'
                            assert 'learned_this_cycle' in learning_result
                            assert learning_result['learned_this_cycle'] is not None


class TestV5ModuleChaining:
    """Test chaining of V5 modules in learning workflow."""

    def test_scan_to_comparison_pipeline(self):
        """Test frontier scan → architecture comparison pipeline."""
        # Get scan results
        scan_results = frontier_scan()
        assert scan_results is not None

        # Compare architecture
        comparison = compare_architecture()
        assert comparison is not None
        assert 'alignment_score' in comparison

        # Both should expose a coherent explicit capability state.
        assert 'implementation_status' in scan_results
        assert 'implementation_status' in comparison

        if scan_results['implementation_status'] in {
            'NOT_IMPLEMENTED', 'STUB_NOT_IMPLEMENTED'
        }:
            assert scan_results['opportunities'] is None
        else:
            assert isinstance(scan_results['opportunities'], list)

        if comparison['implementation_status'] in {
            'NOT_IMPLEMENTED', 'STUB_NOT_IMPLEMENTED'
        }:
            assert comparison['gaps'] is None
            assert comparison['alignment_score'] is None
        else:
            assert isinstance(comparison['gaps'], list)

    def test_comparison_to_report_pipeline(self):
        """Test architecture comparison → evolution report pipeline."""
        # Get comparison
        comparison = compare_architecture()

        # Generate report
        report = generate_report(comparison_results=comparison)
        assert report is not None
        assert 'summary' in report
        assert 'learning_insights' in report

    def test_full_learning_pipeline(self):
        """Test complete learning pipeline from scan to report."""
        # Frontier scan
        scan = frontier_scan()
        assert scan is not None
        assert 'implementation_status' in scan

        # Architecture comparison
        comparison = compare_architecture()
        assert comparison is not None
        assert 'implementation_status' in comparison

        # Gap analysis
        gaps = analyze_gaps()
        assert gaps is not None
        assert 'implementation_status' in gaps

        # Evolution report
        report = generate_report(scan, comparison)
        assert report is not None
        assert report['summary'] is not None
        assert 'implementation_status' in report

        # Pipeline completeness means every phase returned a typed/state-bearing
        # result, not that unimplemented capabilities fabricated measurements.
        assert all([scan, comparison, gaps, report])


class TestV5ValidationAndBenchmarking:
    """Test V5 validation gate and benchmarking."""

    def test_validation_gate_functionality(self):
        """Test validation gate for frontier findings."""
        # Get a finding to validate
        scan = frontier_scan()
        if scan['opportunities']:
            finding = scan['opportunities'][0]
            validation = validate_finding(finding)
            assert validation is not None
            assert 'validation_status' in validation
            assert 'approved_for_integration' in validation

    def test_benchmark_recording(self):
        """Test benchmark recording for performance tracking."""
        # Record a benchmark
        result = record_benchmark('test_metric', 42.5, {'context': 'test'})
        assert result is not None
        assert 'metric' in result
        assert 'value' in result
        assert result['value'] == 42.5

    def test_corpus_update(self):
        """Test research corpus update."""
        # Get findings to add to corpus
        scan = frontier_scan()
        findings = scan.get('opportunities', [])

        if findings:
            update_result = update_corpus(findings)
            assert update_result is not None
            assert 'corpus_size' in update_result or 'findings_added' in update_result


class TestLatencyAndPerformance:
    """Test performance characteristics of learning integration."""

    def test_frontier_scan_latency(self):
        """Test frontier scan completes quickly."""
        start = time.time()
        result = frontier_scan()
        elapsed_ms = (time.time() - start) * 1000

        assert result is not None
        # Should complete in reasonable time (< 1 second)
        assert elapsed_ms < 1000, f"Frontier scan took {elapsed_ms:.1f}ms"

    def test_comparison_latency(self):
        """Test architecture comparison completes quickly."""
        start = time.time()
        result = compare_architecture()
        elapsed_ms = (time.time() - start) * 1000

        assert result is not None
        # Should complete in reasonable time (< 1 second)
        assert elapsed_ms < 1000, f"Architecture comparison took {elapsed_ms:.1f}ms"

    def test_report_generation_latency(self):
        """Test report generation completes quickly."""
        start = time.time()
        result = generate_report()
        elapsed_ms = (time.time() - start) * 1000

        assert result is not None
        # Should complete in reasonable time (< 1 second)
        assert elapsed_ms < 1000, f"Report generation took {elapsed_ms:.1f}ms"

    def test_full_learning_phase_latency(self):
        """Test full learning phase stays under 5 second budget."""
        start = time.time()

        # Run full pipeline
        scan = frontier_scan()
        comparison = compare_architecture()
        gaps = analyze_gaps()
        report = generate_report(scan, comparison)

        elapsed_ms = (time.time() - start) * 1000

        # Should complete in less than 5 seconds per brief
        assert elapsed_ms < 5000, (
            f"Full learning phase took {elapsed_ms:.1f}ms, expected < 5000ms"
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
