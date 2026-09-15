"""Tests for integration_librarian.py"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from systems.engineering_studio.studio_v3.core.project_management import Complexity, Domain, Project, ProjectPhase, ProjectStatus
from systems.engineering_studio.studio_v3.integrations.integration_librarian import (
    DomainKnowledge,
    KnowledgeEntry,
    Lesson,
    LibrarianConnection,
    ProjectKnowledgeExtractor,
)


def make_project(**overrides) -> Project:
    defaults = dict(
        name="Test API Service",
        domain=Domain.API,
        description="A sample project for testing",
        target_standard="professional",
        requirements="Build a REST API",
        success_criteria=["Passes tests"],
        estimated_complexity=Complexity.MEDIUM,
        status=ProjectStatus.COMPLETE,
        current_phase=ProjectPhase.DEPLOYMENT,
        test_coverage=0.97,
        code_review_passed=True,
        security_audit_passed=True,
        audit_report_passed=True,
        performance_verified=True,
        lessons_learned=["Always validate input early"],
        patterns_discovered=["retry-with-backoff"],
        techniques_used=["async-io", "connection-pooling"],
    )
    defaults.update(overrides)
    return Project(**defaults)


# -- KnowledgeEntry ---------------------------------------------------

def test_knowledge_entry_creation():
    entry = KnowledgeEntry(
        type="pattern",
        domain="api",
        timestamp=datetime.now(timezone.utc),
        content={"name": "retry"},
        tags=["resilience"],
        keywords=["retry", "backoff"],
    )
    assert entry.type == "pattern"
    assert entry.domain == "api"
    assert entry.entry_id is not None
    assert entry.content["name"] == "retry"


def test_knowledge_entry_is_frozen():
    entry = KnowledgeEntry(
        type="pattern",
        domain="api",
        timestamp=datetime.now(timezone.utc),
        content={},
    )
    with pytest.raises(Exception):
        entry.type = "other"


def test_knowledge_entry_matches():
    entry = KnowledgeEntry(
        type="pattern",
        domain="api",
        timestamp=datetime.now(timezone.utc),
        content={"description": "circuit breaker for retries"},
        tags=["resilience"],
        keywords=["circuit-breaker"],
    )
    assert entry.matches("circuit")
    assert entry.matches("resilience")
    assert entry.matches("api")
    assert not entry.matches("unrelated-xyz")


# -- LibrarianConnection: save/retrieve --------------------------------

def test_save_and_retrieve_project_knowledge():
    conn = LibrarianConnection()
    project = make_project()
    entry_id = conn.save_project_knowledge(project)
    assert entry_id is not None

    domain_knowledge = conn.retrieve_domain_knowledge(Domain.API.value)
    assert isinstance(domain_knowledge, DomainKnowledge)
    assert domain_knowledge.entry_count == 1
    assert entry_id in domain_knowledge.case_studies


def test_retrieve_domain_knowledge_empty_domain():
    conn = LibrarianConnection()
    dk = conn.retrieve_domain_knowledge("nonexistent-domain")
    assert dk.entry_count == 0
    assert dk.case_studies == []
    assert dk.patterns == []


def test_add_pattern_and_get_patterns_for_domain():
    conn = LibrarianConnection()
    pid = conn.add_pattern("circuit-breaker", {"domain": "api", "tags": ["resilience"]})
    assert pid is not None

    patterns = conn.get_patterns_for_domain("api")
    assert len(patterns) == 1
    assert patterns[0]["name"] == "circuit-breaker"


def test_save_lessons():
    conn = LibrarianConnection()
    lessons = [
        Lesson(description="Use retries", category="pattern", domain="api"),
        Lesson(description="Avoid tight coupling", category="anti-pattern", domain="api"),
    ]
    entry_id = conn.save_lessons(lessons)
    assert entry_id is not None

    dk = conn.retrieve_domain_knowledge("api")
    assert len(dk.lessons) == 2


def test_save_lessons_empty_list():
    conn = LibrarianConnection()
    entry_id = conn.save_lessons([])
    assert entry_id is not None


def test_retrieve_similar_projects():
    conn = LibrarianConnection()
    project = make_project(name="Payments API")
    conn.save_project_knowledge(project)

    similar = conn.retrieve_similar_projects("project_case_study", Domain.API.value)
    assert len(similar) == 1
    assert similar[0]["name"] == "Payments API"


def test_publish_research():
    conn = LibrarianConnection()
    project = make_project()
    entry_id = conn.publish_research(project, {"hypothesis": "faster with pooling", "result": "confirmed"})
    assert entry_id is not None

    results = conn.search_knowledge("pooling")
    assert len(results) == 1


# -- search -------------------------------------------------------------

def test_search_knowledge():
    conn = LibrarianConnection()
    project = make_project(name="Unique Search Target")
    conn.save_project_knowledge(project)

    results = conn.search_knowledge("Unique Search Target")
    assert len(results) == 1
    assert results[0].type == "project_case_study"


def test_search_knowledge_no_match():
    conn = LibrarianConnection()
    project = make_project()
    conn.save_project_knowledge(project)

    results = conn.search_knowledge("totally-unrelated-query-xyz")
    assert results == []


# -- ProjectKnowledgeExtractor -------------------------------------------

def test_extract_from_project():
    extractor = ProjectKnowledgeExtractor()
    project = make_project()
    entry = extractor.extract_from_project(project)

    assert entry.type == "project_case_study"
    assert entry.domain == Domain.API.value
    assert entry.content["name"] == project.name
    assert entry.content["is_complete"] is True


def test_extract_patterns():
    extractor = ProjectKnowledgeExtractor()
    project = make_project()
    patterns = extractor.extract_patterns(project)
    assert len(patterns) == 1
    assert patterns[0]["name"] == "retry-with-backoff"
    assert patterns[0]["domain"] == Domain.API.value


def test_extract_techniques():
    extractor = ProjectKnowledgeExtractor()
    project = make_project()
    techniques = extractor.extract_techniques(project)
    assert techniques == ["async-io", "connection-pooling"]


def test_extract_lessons():
    extractor = ProjectKnowledgeExtractor()
    project = make_project()
    lessons = extractor.extract_lessons(project)

    descriptions = [l.description for l in lessons]
    assert any("validate input early" in d for d in descriptions)
    assert any("retry-with-backoff" in d for d in descriptions)


def test_extract_lessons_flags_low_coverage():
    extractor = ProjectKnowledgeExtractor()
    project = make_project(test_coverage=0.5, status=ProjectStatus.COMPLETE)
    lessons = extractor.extract_lessons(project)
    anti_patterns = [l for l in lessons if l.category == "anti-pattern"]
    assert any("coverage" in l.description for l in anti_patterns)


def test_extract_lessons_flags_failed_security_audit():
    extractor = ProjectKnowledgeExtractor()
    project = make_project(security_audit_passed=False, status=ProjectStatus.COMPLETE)
    lessons = extractor.extract_lessons(project)
    assert any("security audit" in l.description for l in lessons)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
