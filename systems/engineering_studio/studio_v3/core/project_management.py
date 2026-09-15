"""Elite autonomous project management system"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Final
from uuid import UUID, uuid4
import json
import sqlite3


class ProjectStatus(Enum):
    """Project lifecycle status"""
    QUEUED = auto()
    IN_PROGRESS = auto()
    CODE_REVIEW = auto()
    AUDIT = auto()
    TESTING = auto()
    DEPLOYMENT_READY = auto()
    COMPLETE = auto()
    ARCHIVED = auto()


class ProjectPhase(Enum):
    """Current execution phase"""
    REQUIREMENTS = auto()
    ARCHITECTURE = auto()
    IMPLEMENTATION = auto()
    TESTING = auto()
    DOCUMENTATION = auto()
    AUDITING = auto()
    DEPLOYMENT = auto()


class Complexity(Enum):
    """Project complexity level"""
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    EXPERT = auto()


class AuthorityLevel(Enum):
    """Level of authority required to execute a decision"""
    AUTONOMOUS = auto()       # System may act without human sign-off
    COMPLEX = auto()          # Requires elevated review before acting
    REQUIRES_REVIEW = auto()  # Human review mandatory (e.g. breaking changes)
    REQUIRES_HANDOFF = auto()  # Must be handed off entirely to a human


class Domain(Enum):
    """Project domain/type"""
    WEB_BACKEND = "web-backend"
    WEB_FRONTEND = "web-frontend"
    ML_TRAINING = "ml-training"
    ML_INFERENCE = "ml-inference"
    DEVOPS = "devops"
    API = "api"
    CLI = "cli"
    LIBRARY = "library"
    DATA_PIPELINE = "data-pipeline"
    SYSTEM_DESIGN = "system-design"


@dataclass(frozen=True)
class Project:
    """Production project with complete lifecycle tracking"""

    name: str
    domain: Domain
    description: str
    target_standard: str  # "professional", "enterprise", "research"

    # Scope & requirements
    requirements: str
    project_id: Final[UUID] = field(default_factory=uuid4)
    success_criteria: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    estimated_complexity: Complexity = Complexity.MEDIUM

    # Timeline
    created_date: Final[datetime] = field(default_factory=lambda: datetime.now(timezone.utc))
    target_completion: Optional[datetime] = None
    estimated_hours: float = 0.0

    # Execution state
    status: ProjectStatus = ProjectStatus.QUEUED
    current_phase: ProjectPhase = ProjectPhase.REQUIREMENTS
    progress_percentage: float = 0.0

    # Quality tracking
    quality_metrics: Dict[str, float] = field(default_factory=dict)
    test_coverage: float = 0.0
    code_review_passed: bool = False
    security_audit_passed: bool = False
    audit_report_passed: bool = False
    performance_verified: bool = False

    # Deliverables
    repository_url: Optional[str] = None
    documentation_path: Optional[str] = None
    test_results: Optional[str] = None
    audit_report: Optional[str] = None

    # Learning & research
    lessons_learned: List[str] = field(default_factory=list)
    patterns_discovered: List[str] = field(default_factory=list)
    techniques_used: List[str] = field(default_factory=list)
    frontier_alignment: Dict[str, float] = field(default_factory=dict)

    def is_complete(self) -> bool:
        """Project is complete and production-ready"""
        return (
            self.status == ProjectStatus.COMPLETE and
            self.test_coverage >= 0.95 and
            self.code_review_passed and
            self.security_audit_passed and
            self.audit_report_passed and
            self.performance_verified
        )

    def can_progress_to_next_phase(self) -> bool:
        """Check if current phase is complete and ready to proceed"""
        phase_requirements = {
            ProjectPhase.REQUIREMENTS: self.success_criteria and self.target_completion,
            ProjectPhase.ARCHITECTURE: len(self.techniques_used) > 0,
            ProjectPhase.IMPLEMENTATION: self.repository_url is not None,
            ProjectPhase.TESTING: self.test_coverage >= 0.95,
            ProjectPhase.DOCUMENTATION: self.documentation_path is not None,
            ProjectPhase.AUDITING: self.audit_report is not None,
            ProjectPhase.DEPLOYMENT: self.audit_report_passed,
        }
        return phase_requirements.get(self.current_phase, False)


@dataclass(frozen=True)
class DomainExpertise:
    """Codified expertise for a project domain"""

    domain: Domain
    code_coverage_target: float = 0.95
    max_cyclomatic_complexity: int = 10
    performance_targets: Dict[str, float] = field(default_factory=dict)
    security_requirements: List[str] = field(default_factory=list)
    testing_strategy: str = ""
    design_patterns: List[str] = field(default_factory=list)
    anti_patterns: List[str] = field(default_factory=list)
    documentation_requirements: List[str] = field(default_factory=list)
    frontier_techniques: List[str] = field(default_factory=list)
    deployment_checklist: List[str] = field(default_factory=list)

    def verify_compliance(self, project: Project) -> Dict[str, bool]:
        """Verify project meets domain standards"""
        return {
            'code_coverage': project.test_coverage >= self.code_coverage_target,
            'complexity': project.quality_metrics.get('avg_complexity', 0) <= self.max_cyclomatic_complexity,
            'security': project.security_audit_passed,
            'performance': project.performance_verified,
            'documentation': project.documentation_path is not None,
        }


class ProjectPortfolio:
    """Manages multiple concurrent autonomous projects"""

    def __init__(self, db_path: str = '.nexus_projects.db'):
        self.db_path = Path(db_path)
        self.active_projects: Dict[UUID, Project] = {}
        self.completed_projects: List[Project] = []
        self.project_queue: List[Project] = []
        self.domain_expertise: Dict[Domain, DomainExpertise] = {}
        self.cross_project_learnings: List[str] = []
        self._init_database()

    def _init_database(self) -> None:
        """Initialize project tracking database"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                domain TEXT NOT NULL,
                status TEXT NOT NULL,
                current_phase TEXT NOT NULL,
                progress_percentage REAL,
                test_coverage REAL,
                code_review_passed BOOLEAN,
                security_audit_passed BOOLEAN,
                audit_report_passed BOOLEAN,
                performance_verified BOOLEAN,
                created_date DATETIME,
                target_completion DATETIME,
                completion_date DATETIME,
                repository_url TEXT,
                documentation_path TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_phases (
                id INTEGER PRIMARY KEY,
                project_id TEXT,
                phase TEXT NOT NULL,
                started DATETIME,
                completed DATETIME,
                status TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(project_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_lessons (
                id INTEGER PRIMARY KEY,
                project_id TEXT,
                lesson TEXT NOT NULL,
                category TEXT,  -- pattern, technique, anti-pattern, improvement
                learned_date DATETIME,
                FOREIGN KEY(project_id) REFERENCES projects(project_id)
            )
        ''')

        conn.commit()
        conn.close()

    def enqueue_project(self, project: Project) -> UUID:
        """Add project to queue for execution"""
        self.project_queue.append(project)
        self._persist_project(project)
        return project.project_id

    def start_next_project(self) -> Optional[Project]:
        """Start highest-priority project from queue"""
        if not self.project_queue:
            return None

        # Sort by priority: complexity (high first), then created date
        project = sorted(
            self.project_queue,
            key=lambda p: (-p.estimated_complexity.value, p.created_date)
        )[0]

        self.project_queue.remove(project)
        self.active_projects[project.project_id] = project
        return project

    def update_project_progress(
        self,
        project_id: UUID,
        phase: ProjectPhase,
        progress: float,
        metrics: Dict[str, float]
    ) -> None:
        """Update project progress during execution"""
        if project_id not in self.active_projects:
            return

        project = self.active_projects[project_id]

        # Update in-memory project (create new frozen instance)
        updated = Project(
            **{**project.__dict__,
               'current_phase': phase,
               'progress_percentage': progress,
               'quality_metrics': {**project.quality_metrics, **metrics}}
        )

        self.active_projects[project_id] = updated
        self._persist_project(updated)

    def complete_project(self, project_id: UUID, project: Project) -> None:
        """Mark project as complete and move to archive"""
        if project_id in self.active_projects:
            del self.active_projects[project_id]

        self.completed_projects.append(project)
        self._persist_project(project)

    def add_cross_project_learning(self, learning: str) -> None:
        """Record pattern or technique learned across multiple projects"""
        self.cross_project_learnings.append(learning)

    def get_portfolio_status(self) -> Dict[str, any]:
        """Get current portfolio status"""
        return {
            'active_projects': len(self.active_projects),
            'queued_projects': len(self.project_queue),
            'completed_projects': len(self.completed_projects),
            'cross_project_learnings': len(self.cross_project_learnings),
            'active_project_details': [
                {
                    'name': p.name,
                    'domain': p.domain.value,
                    'phase': p.current_phase.name,
                    'progress': p.progress_percentage
                }
                for p in self.active_projects.values()
            ]
        }

    def _persist_project(self, project: Project) -> None:
        """Persist project to database"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO projects
            (project_id, name, domain, status, current_phase, progress_percentage,
             test_coverage, code_review_passed, security_audit_passed,
             audit_report_passed, performance_verified, created_date,
             target_completion, repository_url, documentation_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(project.project_id),
            project.name,
            project.domain.value,
            project.status.name,
            project.current_phase.name,
            project.progress_percentage,
            project.test_coverage,
            project.code_review_passed,
            project.security_audit_passed,
            project.audit_report_passed,
            project.performance_verified,
            project.created_date.isoformat(),
            project.target_completion.isoformat() if project.target_completion else None,
            project.repository_url,
            project.documentation_path
        ))

        conn.commit()
        conn.close()
