"""Professional multi-dimensional system auditor for the Elite Autonomous Engineering Studio.

This module implements :class:`ProfessionalAuditor`, a comprehensive auditing
engine that inspects a software project across seven independent dimensions:
code quality, architecture, performance, security, compliance, testing, and
documentation. Each dimension produces an immutable audit record, and the
records are combined into a single :class:`AuditReport` that carries an
overall production-readiness score, a deployment-readiness verdict, concrete
recommendations, and a final sign-off decision.

The auditor is intentionally static-analysis based (no test execution, no
network calls) so it can run safely and deterministically against any
project directory.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path


# --------------------------------------------------------------------------- #
# Audit dimension dataclasses
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CodeQualityAudit:
    """Results of a static code-quality audit.

    Attributes:
        files_analyzed: Number of source files inspected.
        total_lines: Total non-blank lines of code across analyzed files.
        average_function_length: Mean number of lines per function.
        long_functions: Fully-qualified names of functions exceeding the
            length threshold used for readability (``function_length_limit``).
        complexity_violations: Fully-qualified names of functions whose
            estimated cyclomatic complexity exceeds the configured limit.
        naming_violations: Identifiers that do not follow PEP 8 naming
            conventions.
        duplicate_code_blocks: Number of near-duplicate code blocks detected.
        lint_findings: Human-readable lint-style findings.
        score: Overall code-quality score on a 0-100 scale.
        findings: Free-form textual findings summarizing the audit.
    """

    files_analyzed: int
    total_lines: int
    average_function_length: float
    long_functions: tuple[str, ...]
    complexity_violations: tuple[str, ...]
    naming_violations: tuple[str, ...]
    duplicate_code_blocks: int
    lint_findings: tuple[str, ...]
    score: float
    findings: tuple[str, ...]


@dataclass(frozen=True)
class ArchitectureAudit:
    """Results of an architectural audit.

    Attributes:
        modules_analyzed: Number of Python modules considered.
        circular_dependencies: Pairs of modules involved in circular imports,
            rendered as ``"module_a <-> module_b"`` strings.
        layering_violations: Descriptions of dependency edges that violate
            expected architectural layering (e.g. a low-level module
            importing a high-level orchestrator).
        god_modules: Modules whose size or fan-in/fan-out indicates they are
            doing too much.
        coupling_score: Average afferent+efferent coupling per module.
        cohesion_score: Estimated cohesion score on a 0-100 scale.
        score: Overall architecture score on a 0-100 scale.
        findings: Free-form textual findings summarizing the audit.
    """

    modules_analyzed: int
    circular_dependencies: tuple[str, ...]
    layering_violations: tuple[str, ...]
    god_modules: tuple[str, ...]
    coupling_score: float
    cohesion_score: float
    score: float
    findings: tuple[str, ...]


@dataclass(frozen=True)
class PerformanceAudit:
    """Results of a performance-risk audit.

    Attributes:
        files_analyzed: Number of source files inspected.
        nested_loop_hotspots: Locations with deeply nested loops that risk
            quadratic-or-worse time complexity.
        blocking_io_in_hot_paths: Locations of blocking I/O calls detected
            inside functions that look like hot paths (e.g. request
            handlers, loops).
        inefficient_patterns: Descriptions of known inefficient patterns
            found (e.g. string concatenation in loops, repeated list
            membership tests).
        large_object_allocations: Locations that allocate large in-memory
            structures without apparent streaming/chunking.
        score: Overall performance score on a 0-100 scale.
        findings: Free-form textual findings summarizing the audit.
    """

    files_analyzed: int
    nested_loop_hotspots: tuple[str, ...]
    blocking_io_in_hot_paths: tuple[str, ...]
    inefficient_patterns: tuple[str, ...]
    large_object_allocations: tuple[str, ...]
    score: float
    findings: tuple[str, ...]


@dataclass(frozen=True)
class SecurityAudit:
    """Results of a security audit.

    Attributes:
        files_analyzed: Number of source files inspected.
        hardcoded_secrets: Locations that appear to contain hardcoded
            credentials, API keys, or tokens.
        injection_risks: Locations with patterns vulnerable to injection
            (SQL, shell, code evaluation).
        insecure_deserialization: Locations using unsafe deserialization
            primitives (e.g. ``pickle.loads`` on untrusted input, ``eval``).
        weak_crypto: Locations using deprecated or weak cryptographic
            primitives (e.g. ``md5``, ``sha1`` for security purposes).
        unsafe_permissions: Locations that set overly permissive file or
            network permissions.
        critical_findings: Count of findings classified as critical
            severity.
        high_findings: Count of findings classified as high severity.
        score: Overall security score on a 0-100 scale.
        findings: Free-form textual findings summarizing the audit.
    """

    files_analyzed: int
    hardcoded_secrets: tuple[str, ...]
    injection_risks: tuple[str, ...]
    insecure_deserialization: tuple[str, ...]
    weak_crypto: tuple[str, ...]
    unsafe_permissions: tuple[str, ...]
    critical_findings: int
    high_findings: int
    score: float
    findings: tuple[str, ...]


@dataclass(frozen=True)
class ComplianceAudit:
    """Results of a compliance-verification audit.

    Attributes:
        license_present: Whether a top-level LICENSE file was found.
        readme_present: Whether a top-level README file was found.
        changelog_present: Whether a CHANGELOG file was found.
        contributing_guide_present: Whether a CONTRIBUTING guide was found.
        code_of_conduct_present: Whether a CODE_OF_CONDUCT file was found.
        required_files_missing: Names of required governance files that are
            missing.
        policy_violations: Descriptions of detected policy violations
            (e.g. missing license headers where required).
        score: Overall compliance score on a 0-100 scale.
        findings: Free-form textual findings summarizing the audit.
    """

    license_present: bool
    readme_present: bool
    changelog_present: bool
    contributing_guide_present: bool
    code_of_conduct_present: bool
    required_files_missing: tuple[str, ...]
    policy_violations: tuple[str, ...]
    score: float
    findings: tuple[str, ...]


@dataclass(frozen=True)
class TestingAudit:
    """Results of a testing audit.

    Attributes:
        source_files: Number of source (non-test) Python files.
        test_files: Number of test files discovered.
        test_functions: Number of test functions/methods discovered.
        estimated_coverage_pct: Estimated percentage of source functions
            that have at least one corresponding test, on a 0-100 scale.
        untested_modules: Source modules with no discoverable matching test
            module.
        meets_coverage_gate: Whether estimated coverage meets the 95%
            production gate.
        score: Overall testing score on a 0-100 scale.
        findings: Free-form textual findings summarizing the audit.
    """

    source_files: int
    test_files: int
    test_functions: int
    estimated_coverage_pct: float
    untested_modules: tuple[str, ...]
    meets_coverage_gate: bool
    score: float
    findings: tuple[str, ...]


@dataclass(frozen=True)
class DocumentationAudit:
    """Results of a documentation-completeness audit.

    Attributes:
        public_symbols: Number of public (non-underscore-prefixed) modules,
            classes, and functions discovered.
        documented_symbols: Number of those symbols that have a non-empty
            docstring.
        documentation_coverage_pct: ``documented_symbols / public_symbols``
            expressed as a percentage (0-100).
        undocumented_symbols: Fully-qualified names of public symbols
            lacking a docstring.
        meets_documentation_gate: Whether documentation coverage meets the
            100% production gate.
        score: Overall documentation score on a 0-100 scale.
        findings: Free-form textual findings summarizing the audit.
    """

    public_symbols: int
    documented_symbols: int
    documentation_coverage_pct: float
    undocumented_symbols: tuple[str, ...]
    meets_documentation_gate: bool
    score: float
    findings: tuple[str, ...]


@dataclass(frozen=True)
class AuditReport:
    """Complete, multi-dimensional audit output for a project.

    Attributes:
        project_path: Filesystem path of the audited project.
        code_quality_audit: Code-quality audit results.
        architectural_audit: Architecture audit results.
        performance_audit: Performance audit results.
        security_audit: Security audit results.
        compliance_audit: Compliance audit results.
        testing_audit: Testing audit results.
        documentation_audit: Documentation audit results.
        deployment_readiness: Whether the project is ready to deploy.
        production_readiness_score: Weighted overall score, 0-100.
        recommendations: Prioritized, actionable recommendations.
        sign_off: Final verdict, either ``"APPROVED"`` or ``"NEEDS_WORK"``.
    """

    project_path: str
    code_quality_audit: CodeQualityAudit
    architectural_audit: ArchitectureAudit
    performance_audit: PerformanceAudit
    security_audit: SecurityAudit
    compliance_audit: ComplianceAudit
    testing_audit: TestingAudit
    documentation_audit: DocumentationAudit
    deployment_readiness: bool
    production_readiness_score: float
    recommendations: tuple[str, ...]
    sign_off: str


# --------------------------------------------------------------------------- #
# Weighting constants
# --------------------------------------------------------------------------- #

_DIMENSION_WEIGHTS: dict[str, float] = {
    "code_quality": 0.15,
    "architecture": 0.10,
    "performance": 0.10,
    "security": 0.25,
    "compliance": 0.05,
    "testing": 0.20,
    "documentation": 0.15,
}

_APPROVAL_SCORE_THRESHOLD: float = 90.0
_COVERAGE_GATE_PCT: float = 95.0
_DOCUMENTATION_GATE_PCT: float = 100.0
_FUNCTION_LENGTH_LIMIT: int = 60
_COMPLEXITY_LIMIT: int = 10
_MAX_LOOP_NESTING: int = 3

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*=\s*['\"][A-Za-z0-9_\-/+]{8,}['\"]"),
    re.compile(r"(?i)aws_(access_key_id|secret_access_key)\s*=\s*['\"][^'\"]+['\"]"),
    re.compile(r"-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----"),
)

_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)execute\(\s*['\"].*%s.*['\"]\s*%"),
    re.compile(r"(?i)cursor\.execute\(f['\"]"),
    re.compile(r"os\.system\("),
    re.compile(r"subprocess\.(call|run|Popen)\([^)]*shell\s*=\s*True"),
)

_INSECURE_DESERIALIZATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"pickle\.loads?\("),
    re.compile(r"\byaml\.load\((?!.*Loader=yaml\.SafeLoader)"),
    re.compile(r"\beval\("),
    re.compile(r"\bexec\("),
)

_WEAK_CRYPTO_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"hashlib\.md5\("),
    re.compile(r"hashlib\.sha1\("),
    re.compile(r"\bDES\.new\("),
)

_UNSAFE_PERMISSION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"os\.chmod\([^)]*0o?7{3}\)"),
    re.compile(r"os\.chmod\([^)]*0777\)"),
)

_BLOCKING_IO_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"time\.sleep\("),
    re.compile(r"requests\.(get|post|put|delete)\("),
)

_STRING_CONCAT_IN_LOOP_HINT = re.compile(r"\+=\s*['\"]")

_DEFAULT_EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        "build",
        "dist",
        ".mypy_cache",
        ".pytest_cache",
        ".tox",
        "site-packages",
    }
)


def _iter_python_files(project_root: Path) -> list[Path]:
    """Return all ``.py`` files under ``project_root``, skipping noise directories."""
    files: list[Path] = []
    for path in project_root.rglob("*.py"):
        if any(part in _DEFAULT_EXCLUDED_DIRS for part in path.parts):
            continue
        files.append(path)
    return files


def _safe_read(path: Path) -> str:
    """Read a text file, returning an empty string on any decode/IO failure."""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _safe_parse(source: str) -> ast.Module | None:
    """Parse Python source into an AST, returning ``None`` on a syntax error."""
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def _estimate_complexity(node: ast.AST) -> int:
    """Estimate cyclomatic complexity by counting branching nodes.

    This is a lightweight approximation: it starts at 1 and adds 1 for every
    branching construct (if/for/while/except/boolean-op-operand/comprehension
    condition) encountered in the subtree.
    """
    complexity = 1
    for child in ast.walk(node):
        if isinstance(
            child,
            (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.With, ast.Assert),
        ):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += max(len(child.values) - 1, 0)
        elif isinstance(child, (ast.comprehension,)):
            complexity += 1 + len(child.ifs)
    return complexity


def _max_loop_nesting(node: ast.AST) -> int:
    """Return the maximum depth of nested ``for``/``while`` loops within ``node``."""

    def _depth(n: ast.AST, current: int) -> int:
        best = current
        for child in ast.iter_child_nodes(n):
            if isinstance(child, (ast.For, ast.While)):
                best = max(best, _depth(child, current + 1))
            else:
                best = max(best, _depth(child, current))
        return best

    return _depth(node, 0)


def _is_public_name(name: str) -> bool:
    """Return whether a symbol name is considered public (no leading underscore)."""
    return not name.startswith("_")


# --------------------------------------------------------------------------- #
# Auditor
# --------------------------------------------------------------------------- #


class ProfessionalAuditor:
    """Multi-dimensional static auditor for software projects.

    The auditor walks a project directory, performs seven independent
    static-analysis passes (code quality, architecture, performance,
    security, compliance, testing, documentation), and combines the results
    into a single weighted :class:`AuditReport` with a deployment verdict.

    Each ``_audit_*`` method is self-contained and can be called
    independently; :meth:`audit_system` orchestrates the full pipeline.
    """

    def __init__(self) -> None:
        """Initialize the auditor with no retained state between audits."""
        self._last_report: AuditReport | None = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def audit_system(self, project: str) -> AuditReport:
        """Run the full multi-dimensional audit pipeline on a project.

        Args:
            project: Path to the root directory of the project to audit.

        Returns:
            A complete :class:`AuditReport` covering all seven audit
            dimensions plus an overall readiness score and sign-off.

        Raises:
            FileNotFoundError: If ``project`` does not exist.
            NotADirectoryError: If ``project`` is not a directory.
        """
        project_root = Path(project)
        if not project_root.exists():
            raise FileNotFoundError(f"Project path does not exist: {project}")
        if not project_root.is_dir():
            raise NotADirectoryError(f"Project path is not a directory: {project}")

        code_quality = self._audit_code_quality(project)
        architecture = self._audit_architecture(project)
        performance = self._audit_performance(project)
        security = self._audit_security(project)
        compliance = self._audit_compliance(project)
        testing = self._audit_testing(project)
        documentation = self._audit_documentation(project)
        deployment_ready = self._audit_deployment_readiness(project)

        score = self._calculate_readiness_score(
            code_quality=code_quality,
            architecture=architecture,
            performance=performance,
            security=security,
            compliance=compliance,
            testing=testing,
            documentation=documentation,
        )
        recommendations = self._generate_recommendations(
            code_quality=code_quality,
            architecture=architecture,
            performance=performance,
            security=security,
            compliance=compliance,
            testing=testing,
            documentation=documentation,
        )
        sign_off = self._generate_sign_off(
            score=score,
            security=security,
            testing=testing,
            documentation=documentation,
            deployment_ready=deployment_ready,
        )

        report = AuditReport(
            project_path=str(project_root),
            code_quality_audit=code_quality,
            architectural_audit=architecture,
            performance_audit=performance,
            security_audit=security,
            compliance_audit=compliance,
            testing_audit=testing,
            documentation_audit=documentation,
            deployment_readiness=deployment_ready and sign_off == "APPROVED",
            production_readiness_score=score,
            recommendations=recommendations,
            sign_off=sign_off,
        )
        self._last_report = report
        return report

    # ------------------------------------------------------------------ #
    # Individual audit dimensions
    # ------------------------------------------------------------------ #

    def _audit_code_quality(self, project: str) -> CodeQualityAudit:
        """Audit code quality: function length, complexity, naming, duplication.

        Args:
            project: Path to the project root.

        Returns:
            A :class:`CodeQualityAudit` summarizing the findings.
        """
        files = _iter_python_files(Path(project))
        total_lines = 0
        function_lengths: list[int] = []
        long_functions: list[str] = []
        complexity_violations: list[str] = []
        naming_violations: list[str] = []
        seen_blocks: dict[str, int] = {}
        duplicate_blocks = 0

        for path in files:
            source = _safe_read(path)
            if not source:
                continue
            total_lines += len([ln for ln in source.splitlines() if ln.strip()])
            tree = _safe_parse(source)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    qualname = f"{path.name}:{node.name}"
                    start = node.lineno
                    end = getattr(node, "end_lineno", start)
                    length = max(end - start + 1, 1)
                    function_lengths.append(length)
                    if length > _FUNCTION_LENGTH_LIMIT:
                        long_functions.append(qualname)
                    complexity = _estimate_complexity(node)
                    if complexity > _COMPLEXITY_LIMIT:
                        complexity_violations.append(f"{qualname} (complexity={complexity})")
                    if not re.match(r"^[a-z_][a-z0-9_]*$", node.name):
                        naming_violations.append(qualname)
                    body_key = ast.dump(node, annotate_fields=False)
                    seen_blocks[body_key] = seen_blocks.get(body_key, 0) + 1
                elif isinstance(node, ast.ClassDef):
                    if not re.match(r"^[A-Z][A-Za-z0-9]*$", node.name):
                        naming_violations.append(f"{path.name}:{node.name}")

        duplicate_blocks = sum(1 for count in seen_blocks.values() if count > 1)
        avg_length = sum(function_lengths) / len(function_lengths) if function_lengths else 0.0

        lint_findings: list[str] = []
        if long_functions:
            lint_findings.append(f"{len(long_functions)} function(s) exceed {_FUNCTION_LENGTH_LIMIT} lines")
        if complexity_violations:
            lint_findings.append(f"{len(complexity_violations)} function(s) exceed complexity {_COMPLEXITY_LIMIT}")
        if duplicate_blocks:
            lint_findings.append(f"{duplicate_blocks} duplicate code block(s) detected")

        score = 100.0
        score -= min(len(long_functions) * 2.0, 25.0)
        score -= min(len(complexity_violations) * 3.0, 30.0)
        score -= min(len(naming_violations) * 1.0, 15.0)
        score -= min(duplicate_blocks * 2.0, 20.0)
        score = max(0.0, min(100.0, score))

        findings = tuple(lint_findings) or ("No significant code-quality issues detected.",)

        return CodeQualityAudit(
            files_analyzed=len(files),
            total_lines=total_lines,
            average_function_length=round(avg_length, 2),
            long_functions=tuple(long_functions),
            complexity_violations=tuple(complexity_violations),
            naming_violations=tuple(naming_violations),
            duplicate_code_blocks=duplicate_blocks,
            lint_findings=tuple(lint_findings),
            score=round(score, 2),
            findings=findings,
        )

    def _audit_architecture(self, project: str) -> ArchitectureAudit:
        """Audit architecture: import coupling, circular dependencies, god modules.

        Args:
            project: Path to the project root.

        Returns:
            An :class:`ArchitectureAudit` summarizing the findings.
        """
        project_root = Path(project)
        files = _iter_python_files(project_root)
        module_of: dict[Path, str] = {p: p.stem for p in files}
        imports_by_module: dict[str, set[str]] = {}
        sizes: dict[str, int] = {}

        for path in files:
            mod = module_of[path]
            source = _safe_read(path)
            sizes[mod] = len(source.splitlines())
            tree = _safe_parse(source)
            imports: set[str] = set()
            if tree is not None:
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.add(alias.name.split(".")[0])
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imports.add(node.module.split(".")[0])
            imports_by_module[mod] = imports

        local_modules = set(imports_by_module.keys())
        circular: list[str] = []
        checked_pairs: set[frozenset[str]] = set()
        for mod_a, deps_a in imports_by_module.items():
            for mod_b in deps_a & local_modules:
                if mod_b == mod_a:
                    continue
                pair = frozenset({mod_a, mod_b})
                if pair in checked_pairs:
                    continue
                if mod_a in imports_by_module.get(mod_b, set()):
                    circular.append(f"{mod_a} <-> {mod_b}")
                checked_pairs.add(pair)

        god_modules = [mod for mod, lines in sizes.items() if lines > 800]

        fan_in: dict[str, int] = {mod: 0 for mod in local_modules}
        for deps in imports_by_module.values():
            for dep in deps & local_modules:
                fan_in[dep] = fan_in.get(dep, 0) + 1
        fan_out = {mod: len(deps & local_modules) for mod, deps in imports_by_module.items()}
        total_coupling = sum(fan_in.values()) + sum(fan_out.values())
        coupling_score = total_coupling / max(len(local_modules), 1)

        layering_violations: list[str] = []
        for mod, deps in imports_by_module.items():
            if "cli" in mod.lower() and any("core" not in d.lower() for d in deps if d in local_modules):
                continue  # heuristic placeholder; no strict layering config available

        cohesion_score = max(0.0, 100.0 - coupling_score * 5.0)

        score = 100.0
        score -= min(len(circular) * 10.0, 30.0)
        score -= min(len(god_modules) * 5.0, 25.0)
        score -= min(max(coupling_score - 5.0, 0.0) * 3.0, 25.0)
        score = max(0.0, min(100.0, score))

        findings: list[str] = []
        if circular:
            findings.append(f"{len(circular)} circular dependency pair(s) found")
        if god_modules:
            findings.append(f"{len(god_modules)} oversized module(s) (>800 lines) found")
        if not findings:
            findings.append("No significant architectural issues detected.")

        return ArchitectureAudit(
            modules_analyzed=len(local_modules),
            circular_dependencies=tuple(circular),
            layering_violations=tuple(layering_violations),
            god_modules=tuple(god_modules),
            coupling_score=round(coupling_score, 2),
            cohesion_score=round(cohesion_score, 2),
            score=round(score, 2),
            findings=tuple(findings),
        )

    def _audit_performance(self, project: str) -> PerformanceAudit:
        """Audit performance risk: nested loops, blocking I/O, inefficient patterns.

        Args:
            project: Path to the project root.

        Returns:
            A :class:`PerformanceAudit` summarizing the findings.
        """
        files = _iter_python_files(Path(project))
        nested_loop_hotspots: list[str] = []
        blocking_io: list[str] = []
        inefficient: list[str] = []
        large_allocations: list[str] = []

        for path in files:
            source = _safe_read(path)
            if not source:
                continue
            lines = source.splitlines()
            for lineno, line in enumerate(lines, start=1):
                for pattern in _BLOCKING_IO_PATTERNS:
                    if pattern.search(line):
                        blocking_io.append(f"{path.name}:{lineno}")
                if _STRING_CONCAT_IN_LOOP_HINT.search(line):
                    inefficient.append(f"{path.name}:{lineno} (string concatenation)")
                if re.search(r"=\s*\[\s*\]\s*\*\s*\d{6,}", line) or re.search(r"range\(\d{7,}\)", line):
                    large_allocations.append(f"{path.name}:{lineno}")

            tree = _safe_parse(source)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    depth = _max_loop_nesting(node)
                    if depth >= _MAX_LOOP_NESTING:
                        nested_loop_hotspots.append(f"{path.name}:{node.name} (depth={depth})")

        score = 100.0
        score -= min(len(nested_loop_hotspots) * 5.0, 30.0)
        score -= min(len(blocking_io) * 2.0, 20.0)
        score -= min(len(inefficient) * 1.0, 15.0)
        score -= min(len(large_allocations) * 5.0, 15.0)
        score = max(0.0, min(100.0, score))

        findings: list[str] = []
        if nested_loop_hotspots:
            findings.append(f"{len(nested_loop_hotspots)} deeply nested loop hotspot(s) found")
        if blocking_io:
            findings.append(f"{len(blocking_io)} potential blocking I/O call(s) found")
        if not findings:
            findings.append("No significant performance risks detected.")

        return PerformanceAudit(
            files_analyzed=len(files),
            nested_loop_hotspots=tuple(nested_loop_hotspots),
            blocking_io_in_hot_paths=tuple(blocking_io),
            inefficient_patterns=tuple(inefficient),
            large_object_allocations=tuple(large_allocations),
            score=round(score, 2),
            findings=tuple(findings),
        )

    def _audit_security(self, project: str) -> SecurityAudit:
        """Audit security: hardcoded secrets, injection, unsafe deserialization, crypto.

        Args:
            project: Path to the project root.

        Returns:
            A :class:`SecurityAudit` summarizing the findings.
        """
        files = _iter_python_files(Path(project))
        secrets: list[str] = []
        injection: list[str] = []
        deserialization: list[str] = []
        weak_crypto: list[str] = []
        unsafe_permissions: list[str] = []

        for path in files:
            source = _safe_read(path)
            if not source:
                continue
            for lineno, line in enumerate(source.splitlines(), start=1):
                loc = f"{path.name}:{lineno}"
                if any(p.search(line) for p in _SECRET_PATTERNS):
                    secrets.append(loc)
                if any(p.search(line) for p in _INJECTION_PATTERNS):
                    injection.append(loc)
                if any(p.search(line) for p in _INSECURE_DESERIALIZATION_PATTERNS):
                    deserialization.append(loc)
                if any(p.search(line) for p in _WEAK_CRYPTO_PATTERNS):
                    weak_crypto.append(loc)
                if any(p.search(line) for p in _UNSAFE_PERMISSION_PATTERNS):
                    unsafe_permissions.append(loc)

        critical_findings = len(secrets) + len(injection)
        high_findings = len(deserialization) + len(weak_crypto) + len(unsafe_permissions)

        score = 100.0
        score -= min(critical_findings * 15.0, 70.0)
        score -= min(high_findings * 7.0, 30.0)
        score = max(0.0, min(100.0, score))

        findings: list[str] = []
        if secrets:
            findings.append(f"{len(secrets)} hardcoded secret(s) detected")
        if injection:
            findings.append(f"{len(injection)} injection risk(s) detected")
        if deserialization:
            findings.append(f"{len(deserialization)} insecure deserialization pattern(s) detected")
        if weak_crypto:
            findings.append(f"{len(weak_crypto)} weak cryptographic primitive(s) detected")
        if unsafe_permissions:
            findings.append(f"{len(unsafe_permissions)} unsafe permission setting(s) detected")
        if not findings:
            findings.append("No security issues detected by static analysis.")

        return SecurityAudit(
            files_analyzed=len(files),
            hardcoded_secrets=tuple(secrets),
            injection_risks=tuple(injection),
            insecure_deserialization=tuple(deserialization),
            weak_crypto=tuple(weak_crypto),
            unsafe_permissions=tuple(unsafe_permissions),
            critical_findings=critical_findings,
            high_findings=high_findings,
            score=round(score, 2),
            findings=tuple(findings),
        )

    def _audit_compliance(self, project: str) -> ComplianceAudit:
        """Audit governance/compliance: required project files and policies.

        Args:
            project: Path to the project root.

        Returns:
            A :class:`ComplianceAudit` summarizing the findings.
        """
        project_root = Path(project)

        def _exists_ci(*names: str) -> bool:
            lowered = {p.name.lower() for p in project_root.iterdir()} if project_root.exists() else set()
            return any(name.lower() in lowered for name in names)

        license_present = _exists_ci("LICENSE", "LICENSE.txt", "LICENSE.md")
        readme_present = _exists_ci("README.md", "README.rst", "README.txt", "README")
        changelog_present = _exists_ci("CHANGELOG.md", "CHANGELOG.rst", "CHANGELOG")
        contributing_present = _exists_ci("CONTRIBUTING.md", "CONTRIBUTING.rst")
        code_of_conduct_present = _exists_ci("CODE_OF_CONDUCT.md")

        required = {
            "LICENSE": license_present,
            "README": readme_present,
        }
        missing = tuple(name for name, present in required.items() if not present)

        policy_violations: list[str] = []
        if not license_present:
            policy_violations.append("Missing LICENSE file")
        if not readme_present:
            policy_violations.append("Missing README file")

        score = 100.0
        score -= 40.0 if not license_present else 0.0
        score -= 30.0 if not readme_present else 0.0
        score -= 10.0 if not changelog_present else 0.0
        score -= 10.0 if not contributing_present else 0.0
        score -= 10.0 if not code_of_conduct_present else 0.0
        score = max(0.0, min(100.0, score))

        findings = tuple(policy_violations) or ("All core governance files present.",)

        return ComplianceAudit(
            license_present=license_present,
            readme_present=readme_present,
            changelog_present=changelog_present,
            contributing_guide_present=contributing_present,
            code_of_conduct_present=code_of_conduct_present,
            required_files_missing=missing,
            policy_violations=tuple(policy_violations),
            score=round(score, 2),
            findings=findings,
        )

    def _audit_testing(self, project: str) -> TestingAudit:
        """Audit testing: test-file discovery and estimated source/test coverage mapping.

        Args:
            project: Path to the project root.

        Returns:
            A :class:`TestingAudit` summarizing the findings.
        """
        files = _iter_python_files(Path(project))
        source_files = [
            p for p in files if not (p.name.startswith("test_") or p.name.endswith("_test.py"))
        ]
        test_files = [
            p for p in files if p.name.startswith("test_") or p.name.endswith("_test.py")
        ]

        test_functions = 0
        tested_stems: set[str] = set()
        for path in test_files:
            source = _safe_read(path)
            tree = _safe_parse(source)
            if tree is not None:
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                        test_functions += 1
            stem = path.stem
            if stem.startswith("test_"):
                tested_stems.add(stem[len("test_"):])
            elif stem.endswith("_test"):
                tested_stems.add(stem[: -len("_test")])

        source_stems = {p.stem for p in source_files if p.stem != "__init__"}
        untested = tuple(sorted(source_stems - tested_stems))

        estimated_coverage = (
            100.0 * (len(source_stems) - len(untested)) / len(source_stems) if source_stems else 100.0
        )
        meets_gate = estimated_coverage >= _COVERAGE_GATE_PCT

        score = min(100.0, estimated_coverage)

        findings: list[str] = [
            f"Estimated module-level test coverage: {estimated_coverage:.1f}%",
        ]
        if untested:
            findings.append(f"{len(untested)} source module(s) have no matching test module")
        if not test_files:
            findings.append("No test files discovered in project.")

        return TestingAudit(
            source_files=len(source_files),
            test_files=len(test_files),
            test_functions=test_functions,
            estimated_coverage_pct=round(estimated_coverage, 2),
            untested_modules=untested,
            meets_coverage_gate=meets_gate,
            score=round(score, 2),
            findings=tuple(findings),
        )

    def _audit_documentation(self, project: str) -> DocumentationAudit:
        """Audit documentation: docstring coverage across public API surface.

        Args:
            project: Path to the project root.

        Returns:
            A :class:`DocumentationAudit` summarizing the findings.
        """
        files = _iter_python_files(Path(project))
        public_symbols = 0
        documented_symbols = 0
        undocumented: list[str] = []

        for path in files:
            source = _safe_read(path)
            if not source:
                continue
            tree = _safe_parse(source)
            if tree is None:
                continue

            module_has_docstring = ast.get_docstring(tree) is not None
            public_symbols += 1
            if module_has_docstring:
                documented_symbols += 1
            else:
                undocumented.append(f"{path.name} (module)")

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if not _is_public_name(node.name):
                        continue
                    public_symbols += 1
                    if ast.get_docstring(node):
                        documented_symbols += 1
                    else:
                        undocumented.append(f"{path.name}:{node.name}")

        coverage = 100.0 * documented_symbols / public_symbols if public_symbols else 100.0
        meets_gate = coverage >= _DOCUMENTATION_GATE_PCT

        score = coverage

        findings: list[str] = [f"Documentation coverage: {coverage:.1f}% ({documented_symbols}/{public_symbols})"]
        if undocumented:
            findings.append(f"{len(undocumented)} public symbol(s) lack docstrings")

        return DocumentationAudit(
            public_symbols=public_symbols,
            documented_symbols=documented_symbols,
            documentation_coverage_pct=round(coverage, 2),
            undocumented_symbols=tuple(undocumented),
            meets_documentation_gate=meets_gate,
            score=round(score, 2),
            findings=tuple(findings),
        )

    def _audit_deployment_readiness(self, project: str) -> bool:
        """Determine baseline deployment readiness independent of the numeric score.

        A project is considered deployment-ready at the baseline level when
        it has at least one source file, at least one test file, and no
        unparsable (syntactically invalid) Python files.

        Args:
            project: Path to the project root.

        Returns:
            ``True`` if baseline deployment-readiness conditions are met.
        """
        files = _iter_python_files(Path(project))
        if not files:
            return False

        has_tests = any(p.name.startswith("test_") or p.name.endswith("_test.py") for p in files)
        if not has_tests:
            return False

        for path in files:
            source = _safe_read(path)
            if source and _safe_parse(source) is None:
                return False

        return True

    # ------------------------------------------------------------------ #
    # Aggregation
    # ------------------------------------------------------------------ #

    def _calculate_readiness_score(
        self,
        *,
        code_quality: CodeQualityAudit,
        architecture: ArchitectureAudit,
        performance: PerformanceAudit,
        security: SecurityAudit,
        compliance: ComplianceAudit,
        testing: TestingAudit,
        documentation: DocumentationAudit,
    ) -> float:
        """Compute the weighted overall production-readiness score.

        Args:
            code_quality: Code-quality audit results.
            architecture: Architecture audit results.
            performance: Performance audit results.
            security: Security audit results.
            compliance: Compliance audit results.
            testing: Testing audit results.
            documentation: Documentation audit results.

        Returns:
            A weighted score in the range 0-100.
        """
        weighted_sum = (
            code_quality.score * _DIMENSION_WEIGHTS["code_quality"]
            + architecture.score * _DIMENSION_WEIGHTS["architecture"]
            + performance.score * _DIMENSION_WEIGHTS["performance"]
            + security.score * _DIMENSION_WEIGHTS["security"]
            + compliance.score * _DIMENSION_WEIGHTS["compliance"]
            + testing.score * _DIMENSION_WEIGHTS["testing"]
            + documentation.score * _DIMENSION_WEIGHTS["documentation"]
        )
        return round(max(0.0, min(100.0, weighted_sum)), 2)

    def _generate_recommendations(
        self,
        *,
        code_quality: CodeQualityAudit,
        architecture: ArchitectureAudit,
        performance: PerformanceAudit,
        security: SecurityAudit,
        compliance: ComplianceAudit,
        testing: TestingAudit,
        documentation: DocumentationAudit,
    ) -> tuple[str, ...]:
        """Generate prioritized, actionable recommendations from all audit results.

        Args:
            code_quality: Code-quality audit results.
            architecture: Architecture audit results.
            performance: Performance audit results.
            security: Security audit results.
            compliance: Compliance audit results.
            testing: Testing audit results.
            documentation: Documentation audit results.

        Returns:
            A tuple of recommendation strings, most critical first.
        """
        recommendations: list[str] = []

        if security.critical_findings:
            recommendations.append(
                f"CRITICAL: Remediate {security.critical_findings} critical security finding(s) "
                "(hardcoded secrets and/or injection risks) before deployment."
            )
        if security.high_findings:
            recommendations.append(
                f"HIGH: Address {security.high_findings} high-severity security finding(s) "
                "(insecure deserialization, weak crypto, or unsafe permissions)."
            )
        if not testing.meets_coverage_gate:
            recommendations.append(
                f"Increase test coverage from {testing.estimated_coverage_pct:.1f}% to at least "
                f"{_COVERAGE_GATE_PCT:.0f}% by adding tests for: "
                f"{', '.join(testing.untested_modules[:5]) or 'remaining untested modules'}."
            )
        if not documentation.meets_documentation_gate:
            recommendations.append(
                f"Document all public API surface (currently "
                f"{documentation.documentation_coverage_pct:.1f}% covered, "
                f"{len(documentation.undocumented_symbols)} symbol(s) missing docstrings)."
            )
        if code_quality.complexity_violations:
            recommendations.append(
                f"Refactor {len(code_quality.complexity_violations)} overly complex function(s) "
                "to reduce cyclomatic complexity."
            )
        if code_quality.long_functions:
            recommendations.append(
                f"Break up {len(code_quality.long_functions)} overly long function(s) "
                f"(>{_FUNCTION_LENGTH_LIMIT} lines) into smaller units."
            )
        if architecture.circular_dependencies:
            recommendations.append(
                f"Eliminate {len(architecture.circular_dependencies)} circular dependency pair(s) "
                "to improve modularity."
            )
        if architecture.god_modules:
            recommendations.append(
                f"Split {len(architecture.god_modules)} oversized module(s) into smaller, "
                "single-responsibility modules."
            )
        if performance.nested_loop_hotspots:
            recommendations.append(
                f"Optimize {len(performance.nested_loop_hotspots)} deeply nested loop hotspot(s) "
                "to avoid quadratic-or-worse time complexity."
            )
        if performance.blocking_io_in_hot_paths:
            recommendations.append(
                "Replace blocking I/O calls in hot paths with async or batched alternatives."
            )
        if compliance.required_files_missing:
            recommendations.append(
                f"Add missing governance file(s): {', '.join(compliance.required_files_missing)}."
            )

        if not recommendations:
            recommendations.append("No blocking issues found; project meets production-readiness gates.")

        return tuple(recommendations)

    def _generate_sign_off(
        self,
        *,
        score: float,
        security: SecurityAudit,
        testing: TestingAudit,
        documentation: DocumentationAudit,
        deployment_ready: bool,
    ) -> str:
        """Determine the final sign-off verdict from the overall score and critical gates.

        Approval requires all of:
          - overall score strictly greater than the approval threshold (90.0),
          - zero critical security findings,
          - the test-coverage gate (95%) is met,
          - the documentation gate (100% of public API) is met,
          - baseline deployment readiness is satisfied.

        Args:
            score: Overall weighted production-readiness score.
            security: Security audit results.
            testing: Testing audit results.
            documentation: Documentation audit results.
            deployment_ready: Baseline deployment-readiness verdict.

        Returns:
            ``"APPROVED"`` if all gates pass, otherwise ``"NEEDS_WORK"``.
        """
        gates_passed = (
            score > _APPROVAL_SCORE_THRESHOLD
            and security.critical_findings == 0
            and testing.meets_coverage_gate
            and documentation.meets_documentation_gate
            and deployment_ready
        )
        return "APPROVED" if gates_passed else "NEEDS_WORK"
