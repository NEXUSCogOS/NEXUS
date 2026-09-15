"""
Knowledge Librarian Integration for the Elite Autonomous Engineering Studio.

This module provides the integration layer between the Engineering Studio and
a "knowledge librarian" system responsible for durable storage and retrieval
of project knowledge: case studies, domain expertise, reusable patterns,
lessons learned, and published research.

Design notes
------------
- All knowledge records are immutable (frozen dataclasses) and timestamped.
- The storage backend is stubbed via `_persist_knowledge`, `_retrieve_knowledge`
  and `_search_storage` on `LibrarianConnection`. These are the three
  extension points a real librarian backend (e.g. the NEXUS `Librarian`
  project's ingestion pipeline / vector index) must implement. The current
  implementation is an in-memory mock so this module is independently
  testable and usable without a live librarian service.
- `ProjectKnowledgeExtractor` turns a completed/in-progress `Project` (from
  `project_management.py`) into structured, actionable knowledge entries.

Integration points for a real librarian backend
-------------------------------------------------
Replace the bodies of the three `_*_storage`/`_persist`/`_retrieve` methods
on `LibrarianConnection` with calls into the real system, e.g.:

    - _persist_knowledge -> POST to Librarian ingestion API / write markdown
      + update librarian-index.csv (see ~/Librarian/ingestion/ingest.py)
    - _retrieve_knowledge -> GET by id from Librarian index / vector store
    - _search_storage -> full-text / embedding search against the Librarian
      corpus, returning matching entry ids ranked by relevance

The public method signatures on `LibrarianConnection` are stable and are
not expected to change when the storage backend is swapped.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from ..core.project_management import Project


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class KnowledgeEntry:
    """A single immutable, timestamped unit of stored knowledge.

    Attributes:
        entry_id: Unique identifier assigned at creation time.
        type: Kind of knowledge, e.g. "project_case_study",
            "domain_expertise", "pattern", "lesson", "research".
        domain: The engineering domain this entry belongs to
            (matches `project_management.Domain.value`).
        timestamp: UTC creation time. Entries are immutable; there is no
            "updated_at" — a revision is a new entry.
        content: Arbitrary structured payload for this entry type.
        tags: Free-form labels for coarse filtering.
        keywords: Terms used for full-text search matching.
    """

    type: str
    domain: str
    timestamp: datetime
    content: Dict[str, Any]
    tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    entry_id: UUID = field(default_factory=uuid4)

    def matches(self, query: str) -> bool:
        """Case-insensitive match of `query` against tags/keywords/content text."""
        q = query.lower().strip()
        if not q:
            return False
        if any(q in t.lower() for t in self.tags):
            return True
        if any(q in k.lower() for k in self.keywords):
            return True
        if q in self.type.lower() or q in self.domain.lower():
            return True
        # Shallow scan of stringifiable content values.
        for value in self.content.values():
            try:
                if q in str(value).lower():
                    return True
            except Exception:
                continue
        return False


@dataclass(frozen=True)
class Lesson:
    """A single actionable lesson learned from a project.

    Attributes:
        description: What was learned, stated actionably.
        category: One of "pattern", "technique", "anti-pattern", "improvement".
        domain: Engineering domain the lesson applies to.
        project_id: Source project this lesson was extracted from, if any.
        confidence: Rough confidence/strength of the lesson in [0, 1].
        timestamp: UTC time the lesson was recorded.
    """

    description: str
    category: str = "improvement"
    domain: Optional[str] = None
    project_id: Optional[UUID] = None
    confidence: float = 0.5
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class DomainKnowledge:
    """Aggregated knowledge for a single engineering domain.

    Attributes:
        domain: The domain this aggregation covers.
        case_studies: `KnowledgeEntry` ids of type "project_case_study".
        patterns: Pattern payloads (name -> pattern_data) known for this domain.
        lessons: Lessons recorded against this domain.
        keywords: Union of keywords seen across entries in this domain.
        entry_count: Total number of entries retrieved for this domain.
    """

    domain: str
    case_studies: List[UUID] = field(default_factory=list)
    patterns: List[Dict[str, Any]] = field(default_factory=list)
    lessons: List[Lesson] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    entry_count: int = 0


# ---------------------------------------------------------------------------
# Storage-backed connection
# ---------------------------------------------------------------------------

class LibrarianConnection:
    """Client for saving and retrieving project knowledge via the librarian.

    This implementation ships with an in-memory mock storage layer so the
    Engineering Studio can be developed and tested without a live librarian
    service. Swap the three `_*` storage methods for real backend calls to
    integrate with the actual Librarian system (see module docstring).
    """

    def __init__(self) -> None:
        # Mock storage: entry_id -> KnowledgeEntry
        self._store: Dict[UUID, KnowledgeEntry] = {}
        # Secondary indexes for fast lookup.
        self._by_domain: Dict[str, List[UUID]] = {}
        self._by_type: Dict[str, List[UUID]] = {}

    # -- public API ---------------------------------------------------

    def save_project_knowledge(self, project: Project) -> UUID:
        """Extract and persist a case-study entry for a completed/active project.

        Args:
            project: The project to summarize and store.

        Returns:
            The UUID of the newly persisted `KnowledgeEntry`.
        """
        extractor = ProjectKnowledgeExtractor()
        entry = extractor.extract_from_project(project)
        return self._persist_knowledge(entry)

    def retrieve_domain_knowledge(self, domain: str) -> DomainKnowledge:
        """Aggregate all stored knowledge for a given domain.

        Args:
            domain: Domain value string, e.g. "web-backend".

        Returns:
            A `DomainKnowledge` summary; empty if nothing is stored yet.
        """
        entry_ids = self._by_domain.get(domain, [])
        entries = [self._retrieve_knowledge(eid) for eid in entry_ids]
        entries = [e for e in entries if e is not None]

        case_studies = [e.entry_id for e in entries if e.type == "project_case_study"]
        patterns = [e.content for e in entries if e.type == "pattern"]
        lessons: List[Lesson] = []
        for e in entries:
            if e.type != "lesson":
                continue
            for raw in e.content.get("lessons", []):
                timestamp = raw.get("timestamp")
                lessons.append(Lesson(
                    description=raw.get("description", ""),
                    category=raw.get("category", "improvement"),
                    domain=raw.get("domain", e.domain),
                    project_id=raw.get("project_id"),
                    confidence=raw.get("confidence", 0.5),
                    timestamp=(
                        datetime.fromisoformat(timestamp)
                        if isinstance(timestamp, str) else e.timestamp
                    ),
                ))
        keywords = sorted({kw for e in entries for kw in e.keywords})

        return DomainKnowledge(
            domain=domain,
            case_studies=case_studies,
            patterns=patterns,
            lessons=lessons,
            keywords=keywords,
            entry_count=len(entries),
        )

    def search_knowledge(self, query: str) -> List[KnowledgeEntry]:
        """Search all stored knowledge for entries matching `query`.

        Args:
            query: Free-text search term matched against tags, keywords,
                type, domain, and shallow content values.

        Returns:
            Matching entries, most recent first.
        """
        ids = self._search_storage(query)
        entries = [self._retrieve_knowledge(eid) for eid in ids]
        entries = [e for e in entries if e is not None]
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries

    def add_pattern(self, pattern_name: str, pattern_data: Dict[str, Any]) -> UUID:
        """Persist a reusable design/engineering pattern.

        Args:
            pattern_name: Human-readable pattern identifier, e.g.
                "circuit-breaker-retry".
            pattern_data: Structured pattern payload; should include a
                "domain" key when the pattern is domain-specific.

        Returns:
            The UUID of the persisted pattern entry.
        """
        domain = str(pattern_data.get("domain", "general"))
        content = {"name": pattern_name, **pattern_data}
        entry = KnowledgeEntry(
            type="pattern",
            domain=domain,
            timestamp=datetime.now(timezone.utc),
            content=content,
            tags=list(pattern_data.get("tags", [])) + ["pattern"],
            keywords=list(pattern_data.get("keywords", [])) + [pattern_name],
        )
        return self._persist_knowledge(entry)

    def get_patterns_for_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Retrieve all pattern payloads recorded for a domain.

        Args:
            domain: Domain value string.

        Returns:
            List of pattern content dicts (empty if none stored).
        """
        entry_ids = self._by_domain.get(domain, [])
        entries = [self._retrieve_knowledge(eid) for eid in entry_ids]
        return [e.content for e in entries if e is not None and e.type == "pattern"]

    def save_lessons(self, lessons: List[Lesson]) -> UUID:
        """Persist a batch of lessons as a single knowledge entry.

        Args:
            lessons: One or more `Lesson` records, typically extracted from
                a completed project.

        Returns:
            The UUID of the persisted batch entry. If `lessons` is empty,
            an empty batch entry is still created for auditability.

        Raises:
            ValueError: If lessons come from more than one domain and no
                domain can be inferred, the batch is stored under "general".
        """
        domains = {l.domain for l in lessons if l.domain}
        domain = domains.pop() if len(domains) == 1 else "general"

        content = {
            "lessons": [
                {
                    "description": l.description,
                    "category": l.category,
                    "domain": l.domain,
                    "project_id": l.project_id,
                    "confidence": l.confidence,
                    "timestamp": l.timestamp.isoformat(),
                }
                for l in lessons
            ]
        }
        keywords = list({l.category for l in lessons})
        entry = KnowledgeEntry(
            type="lesson",
            domain=domain,
            timestamp=datetime.now(timezone.utc),
            content=content,
            tags=["lesson"] + list({l.category for l in lessons}),
            keywords=keywords,
        )
        return self._persist_knowledge(entry)

    def retrieve_similar_projects(self, project_type: str, domain: str) -> List[Dict[str, Any]]:
        """Find prior project case studies similar in type and domain.

        Args:
            project_type: Loose project type/category string (matched
                against stored tags/keywords), e.g. "api", "cli".
            domain: Domain value string to restrict the search to.

        Returns:
            List of case-study content dicts, most recent first.
        """
        entry_ids = self._by_domain.get(domain, [])
        entries = [self._retrieve_knowledge(eid) for eid in entry_ids]
        entries = [
            e for e in entries
            if e is not None and e.type == "project_case_study"
            and (project_type.lower() in e.type.lower() or e.matches(project_type))
        ]
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return [e.content for e in entries]

    def publish_research(self, project: Project, findings: Dict[str, Any]) -> UUID:
        """Publish research findings derived from a project.

        Args:
            project: The project the research is derived from.
            findings: Arbitrary structured research payload (hypotheses,
                results, references, etc.).

        Returns:
            The UUID of the persisted research entry.
        """
        content = {
            "project_id": project.project_id,
            "project_name": project.name,
            "findings": findings,
        }
        entry = KnowledgeEntry(
            type="domain_expertise" if findings.get("is_expertise") else "research",
            domain=project.domain.value,
            timestamp=datetime.now(timezone.utc),
            content=content,
            tags=["research", project.domain.value],
            keywords=[project.name] + list(findings.keys()),
        )
        return self._persist_knowledge(entry)

    # -- storage interface (mock; replace for real backend) -----------

    def _persist_knowledge(self, entry: KnowledgeEntry) -> UUID:
        """Persist a knowledge entry to storage.

        Mock implementation: stores in-memory and updates domain/type
        indexes. A real backend should write to the Librarian's durable
        store (e.g. markdown + `librarian-index.csv`, or a database) and
        return the same `entry.entry_id` (persistence must not mutate ids).
        """
        self._store[entry.entry_id] = entry
        self._by_domain.setdefault(entry.domain, []).append(entry.entry_id)
        self._by_type.setdefault(entry.type, []).append(entry.entry_id)
        return entry.entry_id

    def _retrieve_knowledge(self, entry_id: UUID) -> Optional[KnowledgeEntry]:
        """Retrieve a single knowledge entry by id, or None if not found.

        Mock implementation: dictionary lookup. A real backend should
        fetch by id from the durable store/index.
        """
        return self._store.get(entry_id)

    def _search_storage(self, query: str) -> List[UUID]:
        """Return ids of stored entries matching a free-text query.

        Mock implementation: linear scan using `KnowledgeEntry.matches`.
        A real backend should perform full-text or embedding search
        against the Librarian corpus and return ranked entry ids.
        """
        return [eid for eid, entry in self._store.items() if entry.matches(query)]


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

class ProjectKnowledgeExtractor:
    """Extracts structured, actionable knowledge from a `Project`."""

    def extract_from_project(self, project: Project) -> KnowledgeEntry:
        """Build a single "project_case_study" `KnowledgeEntry` from a project.

        Args:
            project: The project to summarize.

        Returns:
            A `KnowledgeEntry` capturing the project's outcome, patterns,
            techniques, and lessons for future retrieval.
        """
        patterns = self.extract_patterns(project)
        techniques = self.extract_techniques(project)
        lessons = self.extract_lessons(project)

        content: Dict[str, Any] = {
            "project_id": project.project_id,
            "name": project.name,
            "description": project.description,
            "domain": project.domain.value,
            "target_standard": project.target_standard,
            "status": project.status.name,
            "complexity": project.estimated_complexity.name,
            "test_coverage": project.test_coverage,
            "is_complete": project.is_complete(),
            "patterns": patterns,
            "techniques": techniques,
            "lessons": [l.description for l in lessons],
            "quality_metrics": dict(project.quality_metrics),
        }

        tags = [project.domain.value, project.status.name.lower(), project.target_standard]
        keywords = list({
            project.name,
            *techniques,
            *(p.get("name", "") for p in patterns),
        })
        keywords = [k for k in keywords if k]

        return KnowledgeEntry(
            type="project_case_study",
            domain=project.domain.value,
            timestamp=datetime.now(timezone.utc),
            content=content,
            tags=tags,
            keywords=keywords,
        )

    def extract_patterns(self, project: Project) -> List[Dict[str, Any]]:
        """Derive reusable pattern records from a project's discovered patterns.

        Args:
            project: The project to inspect.

        Returns:
            One dict per pattern in `project.patterns_discovered`, each
            with at least "name" and "domain" keys.
        """
        return [
            {
                "name": pattern_name,
                "domain": project.domain.value,
                "source_project": project.name,
                "source_project_id": project.project_id,
            }
            for pattern_name in project.patterns_discovered
        ]

    def extract_techniques(self, project: Project) -> List[str]:
        """Return the list of techniques applied on a project.

        Args:
            project: The project to inspect.

        Returns:
            Copy of `project.techniques_used`.
        """
        return list(project.techniques_used)

    def extract_lessons(self, project: Project) -> List[Lesson]:
        """Derive structured `Lesson` records from a project's free-text lessons.

        Args:
            project: The project to inspect.

        Returns:
            One `Lesson` per entry in `project.lessons_learned`, plus any
            implicit lessons inferable from quality outcomes (e.g. low test
            coverage, failed audits).
        """
        lessons = [
            Lesson(
                description=text,
                category="improvement",
                domain=project.domain.value,
                project_id=project.project_id,
                confidence=0.6,
            )
            for text in project.lessons_learned
        ]

        # Implicit lessons from measurable outcomes.
        if project.test_coverage < 0.95 and project.status.name in ("COMPLETE", "ARCHIVED"):
            lessons.append(Lesson(
                description=(
                    f"Project '{project.name}' finished with test coverage "
                    f"{project.test_coverage:.0%}, below the 95% target."
                ),
                category="anti-pattern",
                domain=project.domain.value,
                project_id=project.project_id,
                confidence=0.9,
            ))

        if not project.security_audit_passed and project.status.name in ("COMPLETE", "ARCHIVED"):
            lessons.append(Lesson(
                description=(
                    f"Project '{project.name}' reached {project.status.name} "
                    "without a passing security audit."
                ),
                category="anti-pattern",
                domain=project.domain.value,
                project_id=project.project_id,
                confidence=0.9,
            ))

        for pattern_name in project.patterns_discovered:
            lessons.append(Lesson(
                description=f"Pattern '{pattern_name}' proved effective in '{project.name}'.",
                category="pattern",
                domain=project.domain.value,
                project_id=project.project_id,
                confidence=0.7,
            ))

        return lessons
