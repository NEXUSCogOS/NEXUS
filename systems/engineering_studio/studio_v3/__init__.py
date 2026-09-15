"""Elite Autonomous Engineering Studio v3 - Production Ready

Organized by subsystem for maximum clarity:

CORE SYSTEMS:
  core/ - Semantic foundation, project management, autonomy
  quality/ - Professional review and auditing
  execution/ - Project execution, testing, repair

INTELLIGENCE:
  framework/ - Scientific method, experimentation
  analysis/ - Code metrics, comparisons, detection
  knowledge/ - Knowledge graphs and learning
  learning/ - Enhancement and evolution
  research/ - Frontier research and integration

OPERATIONS:
  operations/ - Scheduling, monitoring, escalation
  platforms/ - CLI, dashboards, controllers
  control/ - Executive decision-making
  records/ - Technical papers, decisions, manifests

INFRASTRUCTURE:
  cognition/ - Planning and prioritization
  perception/ - System scanning
  governance/ - Authority and gating
  memory/ - Data storage and retrieval
  integrations/ - External connections
  utils/ - Config, persistence, metrics

SCIENTIFIC VALIDATION:
  observatory/ - Evidence ledger, resource economics, independent auditing, baseline assessment

TESTING:
  tests/ - Unit and integration tests
"""

from . import core, quality, execution
from .core import (
    SemanticEntity, Auditable, Learnable, EventEmitter, AuditEntry, Decision,
    Project, ProjectPortfolio, ProjectStatus, ProjectPhase, Domain,
    AutonomyLevel, EscalationFramework, AutonomousDecisionMaker
)
from .quality import (
    ProfessionalCodeReviewer, ReviewResult,
    ProfessionalAuditor, AuditReport
)
from .execution import (
    AutonomousProjectExecutor, ExecutionResult,
    ApprovalQueue, AutonomousRecorder, TestRunner, TestResult,
    RepairGenerator, PatchGenerator, SandboxManager
)

__version__ = "3.0.0"
__all__ = [
    # Submodules
    'core', 'quality', 'execution',
    # Core
    'SemanticEntity', 'Auditable', 'Learnable', 'EventEmitter', 'AuditEntry', 'Decision',
    'Project', 'ProjectPortfolio', 'ProjectStatus', 'ProjectPhase', 'Domain',
    'AutonomyLevel', 'EscalationFramework', 'AutonomousDecisionMaker',
    # Quality
    'ProfessionalCodeReviewer', 'ReviewResult',
    'ProfessionalAuditor', 'AuditReport',
    # Execution
    'AutonomousProjectExecutor', 'ExecutionResult',
    'ApprovalQueue', 'AutonomousRecorder', 'TestRunner', 'TestResult',
    'RepairGenerator', 'PatchGenerator', 'SandboxManager'
]
