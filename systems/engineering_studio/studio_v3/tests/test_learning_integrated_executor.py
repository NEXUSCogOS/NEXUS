"""
Tests for learning_integrated_executor.py

Verifies:
- Librarian wired to executor lifecycle (pre/post execution)
- Research layer connected to decisions
- Knowledge graph tracking learning
- Cross-project pattern deduplication and transfer
- Learning velocity metrics
- Frontier research alignment
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from systems.engineering_studio.studio_v3.execution.learning_integrated_executor import (
    LearningIntegratedExecutor,
    LearningMetrics,
)
from systems.engineering_studio.studio_v3.execution.autonomous_project_executor import ExecutionResult
from systems.engineering_studio.studio_v3.integrations.integration_librarian import KnowledgeEntry, Lesson
from systems.engineering_studio.studio_v3.knowledge.unified_knowledge_graph import UnifiedKnowledgeGraph


@pytest.fixture
def executor(tmp_path):
    """Create fresh executor for each test with isolated database"""
    import tempfile
    import os
    # Create a unique database file for each test
    db_file = os.path.join(tmp_path, f"test_kg_{os.getpid()}_{id(executor)}.db")

    # Create executor with custom db path
    exec = LearningIntegratedExecutor()
    # Replace the knowledge graph with one using a unique database
    exec.knowledge_graph.close()
    exec.knowledge_graph = UnifiedKnowledgeGraph(db_file)

    yield exec
    exec.close()


@pytest.fixture
def sample_project():
    """Sample project for testing"""
    return {
        'name': 'Test Learning Project',
        'domain': 'api',
        'description': 'Project to test learning integration',
        'requirements': 'Build a REST API with learning capabilities',
        'project_id': 'proj_learning_test_001'
    }


@pytest.fixture
def success_execution_result():
    """Successful execution result"""
    return ExecutionResult(
        success=True,
        code='def api(): return {"status": "ok"}',
        tests_passing=True,
        coverage=0.95,
        audit_approved=True,
        documentation='# API Service\nA robust REST API',
        deployed=True
    )


# ========================================================================
# TASK 3.1: Librarian Connection Tests
# ========================================================================

def test_executor_initializes_with_librarian(executor):
    """Executor initializes with Librarian connection"""
    assert executor.librarian is not None
    assert hasattr(executor.librarian, 'save_project_knowledge')
    assert hasattr(executor.librarian, 'retrieve_domain_knowledge')


def test_retrieve_domain_knowledge_before_execution(executor, sample_project):
    """Retrieves domain patterns BEFORE project starts"""
    # Seed with a pattern
    executor.librarian.add_pattern('retry-pattern', {
        'domain': 'api',
        'description': 'Retry with backoff'
    })

    # Retrieve patterns before execution
    pre_knowledge = executor._retrieve_domain_knowledge_before_execution('api')

    assert pre_knowledge['domain'] == 'api'
    assert pre_knowledge['patterns_retrieved'] == 1
    assert len(pre_knowledge['patterns']) >= 1


def test_knowledge_retrieval_records_in_knowledge_graph(executor):
    """Pre-execution knowledge retrieval is recorded in knowledge graph"""
    pre_knowledge = executor._retrieve_domain_knowledge_before_execution('api')

    # Verify decision was recorded
    stats = executor.knowledge_graph.get_decision_stats()
    assert stats['decisions']['total_decisions'] > 0


def test_extract_patterns_from_execution(executor, success_execution_result, sample_project):
    """Extracts reusable patterns from successful execution"""
    patterns = executor._extract_patterns_from_execution(success_execution_result, sample_project)

    assert 'code_generation_success' in patterns
    assert 'comprehensive_quality_assurance' in patterns
    assert 'auto_documentation' in patterns

    for pattern_name, pattern_data in patterns.items():
        assert pattern_data.get('domain') == 'api'
        assert 'description' in pattern_data
        assert 'tags' in pattern_data


def test_extract_lessons_from_execution(executor, success_execution_result, sample_project):
    """Extracts lessons learned from execution"""
    lessons = executor._extract_lessons_from_execution(success_execution_result, sample_project)

    assert len(lessons) >= 3  # At least 3 lessons
    assert all(isinstance(l, Lesson) for l in lessons)
    assert all(l.domain == 'api' for l in lessons)
    assert all(l.confidence > 0 for l in lessons)


def test_extract_and_persist_knowledge_to_librarian(executor, success_execution_result, sample_project):
    """Extracts and persists knowledge to Librarian"""
    extraction = executor._extract_and_persist_knowledge(sample_project, success_execution_result)

    assert extraction['patterns_extracted'] > 0
    assert extraction['lessons_extracted'] > 0

    # Verify patterns are now queryable
    patterns = executor.librarian.get_patterns_for_domain('api')
    assert len(patterns) > 0


def test_librarian_persistence_survives_domain_retrieval(executor, success_execution_result, sample_project):
    """Patterns saved by one project are retrieved by another"""
    # Execute first project to save patterns
    extraction = executor._extract_and_persist_knowledge(sample_project, success_execution_result)
    patterns_saved = extraction['patterns_extracted']

    # Clear metrics
    executor.learning_metrics.patterns_learned = 0

    # Simulate second project in same domain
    pre_knowledge = executor._retrieve_domain_knowledge_before_execution('api')

    assert pre_knowledge['patterns_retrieved'] >= patterns_saved


# ========================================================================
# TASK 3.2: Research Layer Connection Tests
# ========================================================================

def test_executor_initializes_with_research_corpus(executor):
    """Executor initializes with the implemented research-corpus interface."""
    assert executor.research_corpus is not None
    assert hasattr(executor.research_corpus, 'add_finding')
    assert hasattr(executor.research_corpus, 'get_patterns')

    # Frontier benchmark comparison is not currently implemented.
    assert not hasattr(executor.research_corpus, 'compare_to_frontier')

def test_validate_against_frontier_research(
        executor, success_execution_result, sample_project):
    """Unavailable frontier validation is represented explicitly."""
    validation = executor._validate_against_frontier_research(
        sample_project, success_execution_result
    )

    assert validation['project'] == sample_project['name']
    assert validation['implementation_status'] == 'NOT_IMPLEMENTED'
    assert validation['available'] is False
    assert validation['decisions_researched'] == 0
    assert validation['frontier_aligned_decisions'] == 0
    assert validation['research_papers_consulted'] == 0
    assert validation['comparisons_recorded'] == 0
    assert validation['reason']
    assert 'compare_to_frontier' in validation['required_capabilities']

def test_research_validation_records_in_knowledge_graph(
        executor, success_execution_result, sample_project):
    """Unavailable validation must not manufacture knowledge-graph evidence."""
    validation = executor._validate_against_frontier_research(
        sample_project, success_execution_result
    )

    assert validation['implementation_status'] == 'NOT_IMPLEMENTED'

    stats = executor.knowledge_graph.get_decision_stats()
    assert stats['decisions']['total_decisions'] == 0

def test_frontier_comparison_recorded(
        executor, success_execution_result, sample_project):
    """No frontier comparison is recorded when comparison is unavailable."""
    validation = executor._validate_against_frontier_research(
        sample_project, success_execution_result
    )

    assert validation['implementation_status'] == 'NOT_IMPLEMENTED'
    assert validation['comparisons_recorded'] == 0

    stats = executor.knowledge_graph.get_decision_stats()
    assert stats['decisions']['total_decisions'] == 0

def test_executor_initializes_with_knowledge_graph(executor):
    """Executor initializes with unified knowledge graph"""
    assert executor.knowledge_graph is not None
    assert hasattr(executor.knowledge_graph, 'record_decision')
    assert hasattr(executor.knowledge_graph, 'record_outcome')


def test_cross_project_pattern_deduplication(executor):
    """Deduplicates patterns across projects"""
    patterns = [
        {'name': 'retry-pattern', 'domain': 'api', 'description': 'Retry with backoff'},
        {'name': 'retry-pattern', 'domain': 'api', 'description': 'Retry with backoff'},  # Duplicate
        {'name': 'circuit-breaker', 'domain': 'api', 'description': 'Circuit breaker'},
    ]

    unique = executor._deduplicate_patterns(patterns)
    assert len(unique) == 2  # Should have 2 unique patterns


def test_enable_cross_project_learning(executor, success_execution_result, sample_project):
    """Enables cross-project pattern transfer"""
    # First execution
    post_exec = executor._extract_and_persist_knowledge(sample_project, success_execution_result)

    # Enable cross-project learning
    transfer = executor._enable_cross_project_learning('api', post_exec)

    assert transfer['domain'] == 'api'
    assert transfer['new_patterns'] > 0
    assert 'deduplication_results' in transfer
    assert transfer['transfer_success_rate'] > 0


def test_learning_metrics_tracked(executor, success_execution_result, sample_project):
    """Learning metrics are properly tracked"""
    initial_metrics = executor.get_learning_metrics()

    # Execute learning workflow
    executor._extract_and_persist_knowledge(sample_project, success_execution_result)
    executor._enable_cross_project_learning('api', {'patterns_extracted': 3, 'lessons_extracted': 2})

    final_metrics = executor.get_learning_metrics()

    assert final_metrics['patterns_learned_total'] > initial_metrics['patterns_learned_total']
    assert final_metrics['patterns_transferred_total'] > initial_metrics['patterns_transferred_total']


def test_knowledge_graph_statistics_comprehensive(executor, success_execution_result, sample_project):
    """Knowledge graph provides comprehensive statistics"""
    executor._extract_and_persist_knowledge(sample_project, success_execution_result)

    stats = executor.get_knowledge_graph_stats()

    assert 'decisions' in stats
    assert 'outcomes' in stats
    assert 'lessons' in stats
    assert 'procedures' in stats
    assert stats['decisions']['total_decisions'] > 0


def test_transfer_learning_enables_knowledge_reuse(executor, success_execution_result):
    """Transfer learning enables knowledge to be applied to new projects"""
    # Project 1: Extract and save knowledge
    project1 = {'name': 'Project A', 'domain': 'api'}
    extraction1 = executor._extract_and_persist_knowledge(project1, success_execution_result)
    assert extraction1['patterns_extracted'] > 0

    # Project 2: Retrieve same domain knowledge
    project2 = {'name': 'Project B', 'domain': 'api'}
    pre_knowledge = executor._retrieve_domain_knowledge_before_execution('api')

    # Patterns from Project 1 should be available to Project 2
    assert pre_knowledge['patterns_retrieved'] > 0
    assert len(pre_knowledge['patterns']) > 0


# ========================================================================
# TASK 3.1 + 3.2 + 3.3: Full Integration Tests
# ========================================================================

def test_full_execution_with_learning(executor, sample_project, success_execution_result):
    """Complete execution with all learning components integrated"""
    # Mock the base executor's execute_project method
    def mock_execute(proj):
        return success_execution_result

    executor.base_executor.execute_project = mock_execute

    # Execute with full learning pipeline
    result = executor.execute_project_with_learning(sample_project)

    # Verify all phases completed
    assert 'execution_id' in result
    assert 'learning' in result
    assert 'pre_execution' in result['learning']
    assert 'execution_result' in result['learning']
    assert 'research_alignment' in result['learning']
    assert 'post_execution' in result['learning']
    assert 'knowledge_transfer' in result['learning']


def test_learning_velocity_calculation(executor, success_execution_result, sample_project):
    """Learning velocity (patterns per hour) is calculated"""
    # Simulate multiple executions
    import time
    for i in range(3):
        project = {**sample_project, 'name': f'Project {i}'}
        executor._extract_and_persist_knowledge(project, success_execution_result)
        time.sleep(1.1)  # Sleep > 1 second to ensure timestamp changes in SQLite

    metrics = executor.get_learning_metrics()
    assert metrics['patterns_learned_total'] >= 3


def test_frontier_research_alignment_metric(
        executor, success_execution_result, sample_project):
    """Unavailable research validation must not increment validation metrics."""
    validation = executor._validate_against_frontier_research(
        sample_project, success_execution_result
    )

    assert validation['implementation_status'] == 'NOT_IMPLEMENTED'

    metrics = executor.get_learning_metrics()
    assert metrics['research_decisions_validated'] == 0

def test_cross_project_deduplication_metric(executor, success_execution_result, sample_project):
    """Cross-project deduplication is tracked"""
    executor._extract_and_persist_knowledge(sample_project, success_execution_result)
    executor._enable_cross_project_learning('api', {'patterns_extracted': 3})

    metrics = executor.get_learning_metrics()
    assert 'cross_project_deduplication_events' in metrics


# ========================================================================
# Acceptance Criteria Verification Tests
# ========================================================================

def test_acceptance_librarian_connected_to_executor_lifecycle(executor, success_execution_result, sample_project):
    """✅ Librarian wired to executor lifecycle"""
    # Pre-execution retrieval
    pre = executor._retrieve_domain_knowledge_before_execution('api')
    assert 'patterns_retrieved' in pre

    # Post-execution persistence
    post = executor._extract_and_persist_knowledge(sample_project, success_execution_result)
    assert 'patterns_extracted' in post


def test_acceptance_cross_project_patterns_auto_retrieved_and_reused(executor, success_execution_result):
    """✅ Cross-project patterns auto-retrieved and reused"""
    # Project 1 saves patterns
    proj1 = {'name': 'Project 1', 'domain': 'api'}
    executor._extract_and_persist_knowledge(proj1, success_execution_result)

    # Project 2 retrieves them
    pre_knowledge = executor._retrieve_domain_knowledge_before_execution('api')

    assert pre_knowledge['patterns_retrieved'] > 0


def test_acceptance_research_layer_connected_to_decisions(
        executor, success_execution_result, sample_project):
    """Research integration fails closed until benchmark comparison exists."""
    validation = executor._validate_against_frontier_research(
        sample_project, success_execution_result
    )

    assert validation['implementation_status'] == 'NOT_IMPLEMENTED'
    assert validation['available'] is False
    assert validation['decisions_researched'] == 0
    assert validation['research_papers_consulted'] == 0

def test_acceptance_knowledge_graph_deduplicating_patterns(executor):
    """✅ Knowledge graph deduplicating and discovering patterns"""
    patterns_input = [
        {'name': 'pattern-a', 'domain': 'api'},
        {'name': 'pattern-a', 'domain': 'api'},  # Duplicate
        {'name': 'pattern-b', 'domain': 'api'},
    ]

    unique = executor._deduplicate_patterns(patterns_input)
    assert len(unique) == 2


def test_acceptance_transfer_learning_working_across_projects(executor, success_execution_result):
    """✅ Transfer learning working across projects"""
    # Project A in domain 'api'
    projA = {'name': 'ProjectA', 'domain': 'api'}
    executor._extract_and_persist_knowledge(projA, success_execution_result)

    # Project B queries same domain
    pre_knowledge = executor._retrieve_domain_knowledge_before_execution('api')

    # Project A's knowledge should be available
    assert pre_knowledge['patterns_retrieved'] > 0


def test_acceptance_all_learning_tracked_and_measurable(executor, success_execution_result, sample_project):
    """✅ All learning tracked and measurable"""
    executor._extract_and_persist_knowledge(sample_project, success_execution_result)
    executor._validate_against_frontier_research(sample_project, success_execution_result)
    executor._enable_cross_project_learning('api', {'patterns_extracted': 2})

    metrics = executor.get_learning_metrics()

    # All these should be tracked
    assert 'patterns_learned_total' in metrics
    assert 'patterns_transferred_total' in metrics
    assert 'lessons_extracted_total' in metrics
    assert 'research_decisions_validated' in metrics
    assert 'cross_project_deduplication_events' in metrics
    assert 'learning_velocity_patterns_per_hour' in metrics


def test_acceptance_frontier_research_comparison_documented(
        executor, success_execution_result, sample_project):
    """Frontier-comparison unavailability is explicitly documented."""
    validation = executor._validate_against_frontier_research(
        sample_project, success_execution_result
    )

    assert validation['implementation_status'] == 'NOT_IMPLEMENTED'
    assert validation['available'] is False
    assert validation['comparisons_recorded'] == 0
    assert validation['frontier_aligned_decisions'] == 0
    assert validation['reason']
    assert 'provenanced_frontier_benchmark_corpus' in (
        validation['required_capabilities']
    )

