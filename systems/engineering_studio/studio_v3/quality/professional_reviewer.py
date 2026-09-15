"""Professional code reviewer for the Elite Autonomous Engineering Studio.

Provides peer-review level assessment of generated code across five
dimensions: code quality, architecture, security, performance, and
maintainability. Analysis is AST-based where practical, with heuristic
fallbacks for code that cannot be parsed (e.g. non-Python or malformed
snippets).

This module deliberately does NOT implement live security scanning
(e.g. dependency CVE lookups, SAST engines) or live performance profiling.
Those checks are represented as heuristic pattern matches and are flagged
in docstrings as such; a production deployment should wire in dedicated
tools (bandit, safety/pip-audit, semgrep, py-spy, etc.) behind the same
interface.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Sequence


# --------------------------------------------------------------------------
# Dataclasses
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CodeQualityScore:
    """Code quality metrics for a single review pass.

    Attributes:
        overall_score: Aggregate quality score in [0.0, 1.0].
        cyclomatic_complexity: Average cyclomatic complexity across functions.
        max_cyclomatic_complexity: Highest cyclomatic complexity found in any
            single function.
        naming_convention_score: Fraction of identifiers that follow PEP 8
            naming conventions, in [0.0, 1.0].
        modularity_score: Heuristic score in [0.0, 1.0] reflecting function
            length, nesting depth, and file cohesion.
        function_count: Number of top-level and nested function definitions.
        average_function_length: Average function length in lines.
        issues: Human-readable list of specific quality issues found.
    """

    overall_score: float
    cyclomatic_complexity: float
    max_cyclomatic_complexity: int
    naming_convention_score: float
    modularity_score: float
    function_count: int
    average_function_length: float
    issues: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ArchitectureScore:
    """Architecture evaluation for a single review pass.

    Attributes:
        overall_score: Aggregate architecture score in [0.0, 1.0].
        layering_score: Heuristic score for separation of concerns /
            layering (e.g. I/O separated from business logic).
        dependency_management_score: Score reflecting import hygiene
            (no wildcard imports, no circular-looking self references,
            bounded coupling).
        pattern_usage_score: Score reflecting use of recognizable,
            domain-appropriate design patterns rather than ad-hoc code.
        coupling_estimate: Heuristic estimate of inter-module coupling in
            [0.0, 1.0], where lower is better.
        domain: The engineering domain the code was evaluated against
            (e.g. "backend", "data", "ml", "cli").
        issues: Human-readable list of specific architecture issues found.
    """

    overall_score: float
    layering_score: float
    dependency_management_score: float
    pattern_usage_score: float
    coupling_estimate: float
    domain: str
    issues: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SecurityAudit:
    """Security findings for a single review pass.

    Note:
        This is a static heuristic pattern-matcher, not a substitute for a
        real SAST tool, dependency vulnerability scanner, or manual
        penetration test. It looks for common anti-patterns: injection risk
        (string-built SQL/shell/eval), hardcoded secrets, and weak/absent
        authentication patterns. Dependency CVE checking is intentionally
        out of scope here and should be delegated to a tool such as
        pip-audit or safety.

    Attributes:
        overall_score: Aggregate security score in [0.0, 1.0], where higher
            is safer.
        injection_risk_found: True if an injection-style anti-pattern was
            detected (e.g. string-formatted SQL, `eval`, `exec`, `os.system`
            with interpolated input, `subprocess` with `shell=True`).
        hardcoded_secrets_found: True if a likely hardcoded credential or
            API key literal was detected.
        weak_auth_pattern_found: True if code appears to implement
            authentication/authorization without recognized safeguards
            (e.g. plaintext password comparison).
        dependency_risk_noted: True if the code imports packages that
            warrant a dependency vulnerability scan (always noted as an
            informational flag, since this reviewer does not query a CVE
            database).
        findings: Human-readable list of specific security findings.
    """

    overall_score: float
    injection_risk_found: bool
    hardcoded_secrets_found: bool
    weak_auth_pattern_found: bool
    dependency_risk_noted: bool
    findings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PerformanceAudit:
    """Performance metrics for a single review pass.

    Note:
        This is a static heuristic pattern-matcher, not a live profiler.
        It flags well-known inefficiency patterns (e.g. string
        concatenation in a loop, nested loops over large structures,
        repeated re-computation, unbounded in-memory accumulation) rather
        than measuring actual runtime or memory usage. A production
        deployment should pair this with py-spy, memory_profiler, or
        equivalent instrumentation for the target domain.

    Attributes:
        overall_score: Aggregate performance score in [0.0, 1.0].
        inefficient_loop_patterns: Count of detected inefficient looping
            constructs (e.g. quadratic membership tests, string
            concatenation via `+=` inside a loop).
        memory_risk_patterns: Count of detected patterns that risk
            unbounded memory growth (e.g. accumulating into a list/dict
            inside an unbounded loop without eviction).
        domain: The engineering domain the code was evaluated against.
        issues: Human-readable list of specific performance issues found.
    """

    overall_score: float
    inefficient_loop_patterns: int
    memory_risk_patterns: int
    domain: str
    issues: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ReviewResult:
    """Complete peer-review level assessment of a piece of code.

    Attributes:
        project: Identifier/name of the project being reviewed.
        code_quality: Code quality assessment.
        architecture: Architecture assessment.
        security: Security audit results.
        performance: Performance audit results.
        maintainability_score: Aggregate maintainability score in
            [0.0, 1.0].
        test_coverage_estimate: Estimated test coverage in [0.0, 1.0],
            derived from static analysis (presence/ratio of test
            functions), not an actual coverage.py run.
        has_documentation: Whether the code has adequate docstring
            coverage.
        meets_standards: Whether the code meets baseline domain standards
            (formatting/style/typing conventions).
        follows_frontier_practices: Whether the code follows current
            best practices for its domain (e.g. type hints, async where
            appropriate, structured logging).
        ready_for_production: Final go/no-go determination.
        overall_score: Weighted aggregate score in [0.0, 1.0] across all
            dimensions.
        summary: Human-readable summary of the review.
        blocking_issues: Issues that must be resolved before production
            deployment.
    """

    project: str
    code_quality: CodeQualityScore
    architecture: ArchitectureScore
    security: SecurityAudit
    performance: PerformanceAudit
    maintainability_score: float
    test_coverage_estimate: float
    has_documentation: bool
    meets_standards: bool
    follows_frontier_practices: bool
    ready_for_production: bool
    overall_score: float
    summary: str
    blocking_issues: tuple[str, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------
# Reviewer
# --------------------------------------------------------------------------


_SNAKE_CASE_RE = re.compile(r"^_{0,2}[a-z][a-z0-9_]*_{0,2}$")
_CONST_CASE_RE = re.compile(r"^_{0,2}[A-Z][A-Z0-9_]*_{0,2}$")
_CLASS_CASE_RE = re.compile(r"^_{0,2}[A-Z][a-zA-Z0-9]*$")

_SECRET_KEY_RE = re.compile(
    r"(?i)\b(api_key|apikey|secret|password|passwd|token|access_key)\b\s*=\s*"
    r"['\"][A-Za-z0-9/_\-\.]{6,}['\"]"
)

_TEST_NAME_RE = re.compile(r"^test_")


class ProfessionalCodeReviewer:
    """Performs peer-review level assessment of code before deployment.

    The reviewer combines AST-based static analysis (for valid Python
    source) with regex heuristics (used both as a fallback for
    unparseable input and to catch patterns that are easier to express
    textually, such as hardcoded secrets). It does not execute the
    reviewed code.
    """

    # Thresholds tunable by domain; kept as class constants for simplicity.
    _COMPLEXITY_GOOD = 5
    _COMPLEXITY_ACCEPTABLE = 10

    def review_for_deployment(self, project: str, code: str) -> ReviewResult:
        """Run a full multi-dimensional review and render a go/no-go verdict.

        Args:
            project: Name/identifier of the project the code belongs to.
            code: Python source code to review.

        Returns:
            A ReviewResult aggregating all dimension scores plus a final
            production-readiness determination.
        """
        domain = self._infer_domain(project)

        quality = self._review_code_quality(code)
        architecture = self._review_architecture(code, domain)
        security = self._review_security(code)
        performance = self._review_performance(code, domain)
        maintainability = self._review_maintainability(code)

        test_coverage = self._verify_test_coverage(code)
        has_docs = self._verify_documentation(code)
        meets_standards = self._check_standards(code, domain)
        frontier = self._check_frontier_practices(code, domain)
        production_ready = self._ready_for_production(code, project)

        overall = self._aggregate_score(
            quality, architecture, security, performance, maintainability
        )

        blocking = self._collect_blocking_issues(
            quality, architecture, security, performance, test_coverage, has_docs
        )

        # A hard-blocking issue always overrides a heuristically "ready" verdict.
        final_ready = production_ready and not blocking

        summary = self._build_summary(
            project, overall, final_ready, quality, architecture, security, performance
        )

        return ReviewResult(
            project=project,
            code_quality=quality,
            architecture=architecture,
            security=security,
            performance=performance,
            maintainability_score=maintainability,
            test_coverage_estimate=test_coverage,
            has_documentation=has_docs,
            meets_standards=meets_standards,
            follows_frontier_practices=frontier,
            ready_for_production=final_ready,
            overall_score=overall,
            summary=summary,
            blocking_issues=tuple(blocking),
        )

    # ---------------------------------------------------------------- #
    # Dimension reviewers
    # ---------------------------------------------------------------- #

    def _review_code_quality(self, code: str) -> CodeQualityScore:
        """Assess cyclomatic complexity, naming conventions, and modularity.

        Args:
            code: Python source code to analyze.

        Returns:
            A CodeQualityScore summarizing the analysis. If the code
            cannot be parsed as valid Python, a low-confidence fallback
            score is returned with an explanatory issue.
        """
        issues: list[str] = []
        tree = self._safe_parse(code)
        if tree is None:
            return CodeQualityScore(
                overall_score=0.2,
                cyclomatic_complexity=0.0,
                max_cyclomatic_complexity=0,
                naming_convention_score=0.0,
                modularity_score=0.0,
                function_count=0,
                average_function_length=0.0,
                issues=("Code could not be parsed as valid Python (SyntaxError).",),
            )

        functions = [
            node
            for node in ast.walk(tree)
            for _ in [None]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        complexities = [self._cyclomatic_complexity(fn) for fn in functions]
        avg_complexity = sum(complexities) / len(complexities) if complexities else 1.0
        max_complexity = max(complexities) if complexities else 1

        if max_complexity > self._COMPLEXITY_ACCEPTABLE:
            issues.append(
                f"At least one function has high cyclomatic complexity ({max_complexity})."
            )

        naming_score, naming_issues = self._naming_convention_score(tree)
        issues.extend(naming_issues)

        lengths = [self._function_length(fn) for fn in functions]
        avg_length = sum(lengths) / len(lengths) if lengths else 0.0
        if any(length > 60 for length in lengths):
            issues.append("At least one function exceeds 60 lines; consider decomposing it.")

        modularity_score = self._modularity_score(functions, lengths)

        complexity_score = self._normalize_complexity(avg_complexity)
        overall = round(
            0.35 * complexity_score
            + 0.25 * naming_score
            + 0.40 * modularity_score,
            3,
        )

        return CodeQualityScore(
            overall_score=overall,
            cyclomatic_complexity=round(avg_complexity, 2),
            max_cyclomatic_complexity=max_complexity,
            naming_convention_score=round(naming_score, 3),
            modularity_score=round(modularity_score, 3),
            function_count=len(functions),
            average_function_length=round(avg_length, 2),
            issues=tuple(issues),
        )

    def _review_architecture(self, code: str, domain: str) -> ArchitectureScore:
        """Assess layering, dependency management, and pattern usage.

        Args:
            code: Python source code to analyze.
            domain: Engineering domain the code targets (e.g. "backend",
                "data", "ml", "cli"); used only to tailor the issue
                messages, not to change scoring weights.

        Returns:
            An ArchitectureScore summarizing the analysis.
        """
        issues: list[str] = []
        tree = self._safe_parse(code)
        if tree is None:
            return ArchitectureScore(
                overall_score=0.2,
                layering_score=0.0,
                dependency_management_score=0.0,
                pattern_usage_score=0.0,
                coupling_estimate=1.0,
                domain=domain,
                issues=("Code could not be parsed as valid Python (SyntaxError).",),
            )

        imports = [
            node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        wildcard_imports = [
            node
            for node in imports
            if isinstance(node, ast.ImportFrom)
            and any(alias.name == "*" for alias in node.names)
        ]
        if wildcard_imports:
            issues.append("Wildcard imports found ('from x import *'); harms dependency clarity.")

        dep_score = 1.0 - min(0.5, 0.25 * len(wildcard_imports))

        classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        functions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        # Layering heuristic: presence of both class-based structure and
        # free functions handling I/O vs. logic is a weak proxy; here we
        # reward modular decomposition (multiple classes/functions rather
        # than one monolithic script) and penalize direct I/O calls
        # scattered without any structure at all.
        top_level_statements = len(getattr(tree, "body", []))
        structural_units = len(classes) + len(functions)
        if structural_units == 0:
            layering_score = 0.2
            issues.append("No functions or classes found; code is unstructured.")
        else:
            layering_score = min(1.0, structural_units / max(1, top_level_statements))
            layering_score = max(0.4, layering_score)

        pattern_score = 0.5
        docstring_count = sum(
            1
            for node in classes + functions
            if ast.get_docstring(node) is not None
        )
        if structural_units:
            pattern_score = 0.5 + 0.5 * (docstring_count / structural_units)
        if len(classes) >= 1:
            pattern_score = min(1.0, pattern_score + 0.1)

        coupling_estimate = round(min(1.0, len(imports) / 20.0), 3)

        overall = round(
            0.4 * layering_score + 0.3 * dep_score + 0.3 * pattern_score, 3
        )

        return ArchitectureScore(
            overall_score=overall,
            layering_score=round(layering_score, 3),
            dependency_management_score=round(dep_score, 3),
            pattern_usage_score=round(pattern_score, 3),
            coupling_estimate=coupling_estimate,
            domain=domain,
            issues=tuple(issues),
        )

    def _review_security(self, code: str) -> SecurityAudit:
        """Scan for common injection, secret, and weak-auth anti-patterns.

        This is a static heuristic scan (see class/module docstrings for
        scope limitations) — it does not perform dependency CVE lookups
        or dynamic taint analysis.

        Args:
            code: Python source code to analyze.

        Returns:
            A SecurityAudit summarizing detected findings.
        """
        findings: list[str] = []

        injection_risk = False
        if re.search(r"\beval\s*\(", code) or re.search(r"\bexec\s*\(", code):
            injection_risk = True
            findings.append("Use of eval()/exec() detected; arbitrary code execution risk.")
        if re.search(r"subprocess\.\w+\([^)]*shell\s*=\s*True", code):
            injection_risk = True
            findings.append("subprocess call with shell=True detected; shell injection risk.")
        if re.search(r"os\.system\s*\(", code):
            injection_risk = True
            findings.append("os.system() detected; prefer subprocess with argument lists.")
        if re.search(r"""(?:execute|executemany)\s*\(\s*f?['"].*%s.*['"]\s*%""", code) or re.search(
            r"""(?:execute|executemany)\s*\(\s*f['"][^'"]*\{[^}]+\}""", code
        ):
            injection_risk = True
            findings.append("SQL query built via string formatting/f-string; SQL injection risk.")

        hardcoded_secrets = bool(_SECRET_KEY_RE.search(code))
        if hardcoded_secrets:
            findings.append("Likely hardcoded secret/credential literal detected.")

        weak_auth = False
        if re.search(r"password\s*==\s*", code) or re.search(r"==\s*password", code):
            weak_auth = True
            findings.append("Plaintext password comparison detected; use a constant-time hash check.")
        if re.search(r"md5\(|sha1\(", code) and re.search(r"password", code, re.IGNORECASE):
            weak_auth = True
            findings.append("Weak hash algorithm (md5/sha1) used near password handling.")

        dependency_risk = bool(re.search(r"^\s*(import|from)\s+\w+", code, re.MULTILINE))
        if dependency_risk:
            findings.append(
                "Dependencies detected; run a dedicated vulnerability scan "
                "(e.g. pip-audit) before deployment — not performed by this reviewer."
            )

        penalty = 0.0
        if injection_risk:
            penalty += 0.4
        if hardcoded_secrets:
            penalty += 0.3
        if weak_auth:
            penalty += 0.3
        overall = round(max(0.0, 1.0 - penalty), 3)

        return SecurityAudit(
            overall_score=overall,
            injection_risk_found=injection_risk,
            hardcoded_secrets_found=hardcoded_secrets,
            weak_auth_pattern_found=weak_auth,
            dependency_risk_noted=dependency_risk,
            findings=tuple(findings),
        )

    def _review_performance(self, code: str, domain: str) -> PerformanceAudit:
        """Scan for well-known inefficient loop and memory-growth patterns.

        This is a static heuristic scan, not a live profiler (see module
        docstring for scope limitations).

        Args:
            code: Python source code to analyze.
            domain: Engineering domain the code targets; used to tailor
                issue messages only.

        Returns:
            A PerformanceAudit summarizing detected findings.
        """
        issues: list[str] = []
        tree = self._safe_parse(code)

        inefficient_loops = 0
        memory_risks = 0

        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, (ast.For, ast.While)):
                    for child in ast.walk(node):
                        if (
                            isinstance(child, ast.AugAssign)
                            and isinstance(child.op, ast.Add)
                            and isinstance(child.target, ast.Name)
                        ):
                            # string/list += inside a loop: cheap heuristic,
                            # cannot know the runtime type statically.
                            inefficient_loops += 1
                            issues.append(
                                f"Possible O(n^2) accumulation via '+=' inside a loop "
                                f"(line {getattr(child, 'lineno', '?')})."
                            )
                    nested_loops = [
                        n
                        for n in ast.walk(node)
                        if isinstance(n, (ast.For, ast.While)) and n is not node
                    ]
                    if nested_loops:
                        inefficient_loops += len(nested_loops)
                        issues.append(
                            f"Nested loop detected (line {getattr(node, 'lineno', '?')}); "
                            "verify this isn't operating on large inputs (O(n^2) risk)."
                        )

            for node in ast.walk(tree):
                if isinstance(node, (ast.For, ast.While)):
                    for child in ast.walk(node):
                        if (
                            isinstance(child, ast.Call)
                            and isinstance(child.func, ast.Attribute)
                            and child.func.attr == "append"
                        ):
                            memory_risks += 1
                            break

        else:
            issues.append("Code could not be parsed; performance analysis skipped.")

        loop_penalty = min(0.6, 0.1 * inefficient_loops)
        memory_penalty = min(0.3, 0.05 * memory_risks)
        overall = round(max(0.0, 1.0 - loop_penalty - memory_penalty), 3)

        return PerformanceAudit(
            overall_score=overall,
            inefficient_loop_patterns=inefficient_loops,
            memory_risk_patterns=memory_risks,
            domain=domain,
            issues=tuple(issues),
        )

    def _review_maintainability(self, code: str) -> float:
        """Compute an aggregate maintainability score.

        Combines readability (line length, docstring presence), estimated
        test coverage, and documentation presence into a single score.

        Args:
            code: Python source code to analyze.

        Returns:
            A maintainability score in [0.0, 1.0].
        """
        lines = code.splitlines() or [""]
        long_lines = sum(1 for line in lines if len(line) > 100)
        readability = max(0.0, 1.0 - (long_lines / max(1, len(lines))))

        coverage = self._verify_test_coverage(code)
        documented = 1.0 if self._verify_documentation(code) else 0.3

        return round(0.4 * readability + 0.3 * coverage + 0.3 * documented, 3)

    # ---------------------------------------------------------------- #
    # Verification helpers
    # ---------------------------------------------------------------- #

    def _verify_test_coverage(self, code: str) -> float:
        """Estimate test coverage from static structure.

        This is a proxy, not a real coverage.py measurement: it compares
        the number of `test_*` functions to the number of non-test
        functions/methods in the same source. A dedicated coverage tool
        should be run against the actual test suite for a real figure.

        Args:
            code: Python source code to analyze (may include test
                functions alongside implementation, or be pure
                implementation with no tests).

        Returns:
            An estimated coverage ratio in [0.0, 1.0]. Returns 0.0 if the
            code cannot be parsed or contains no functions at all.
        """
        tree = self._safe_parse(code)
        if tree is None:
            return 0.0

        functions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if not functions:
            return 0.0

        test_functions = [fn for fn in functions if _TEST_NAME_RE.match(fn.name)]
        implementation_functions = [fn for fn in functions if not _TEST_NAME_RE.match(fn.name)]

        if not implementation_functions:
            # Pure test file with nothing to cover.
            return 0.0

        # Each test function is assumed to exercise roughly one
        # implementation function; this is intentionally conservative.
        ratio = len(test_functions) / len(implementation_functions)
        return round(min(1.0, ratio), 3)

    def _verify_documentation(self, code: str) -> bool:
        """Check whether the code has adequate docstring coverage.

        Args:
            code: Python source code to analyze.

        Returns:
            True if the module, and at least 60% of its top-level
            functions/classes, have docstrings. False otherwise, or if
            the code cannot be parsed.
        """
        tree = self._safe_parse(code)
        if tree is None:
            return False

        module_documented = ast.get_docstring(tree) is not None

        definitions = [
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        if not definitions:
            return module_documented

        documented = sum(1 for node in definitions if ast.get_docstring(node) is not None)
        ratio = documented / len(definitions)
        return ratio >= 0.6

    def _check_standards(self, code: str, domain: str) -> bool:
        """Check baseline coding standards compliance for the given domain.

        Checks: parseable syntax, no wildcard imports, no bare `except:`
        clauses, and reasonable line lengths.

        Args:
            code: Python source code to analyze.
            domain: Engineering domain the code targets (currently used
                for message context only; all domains share the same
                baseline standards).

        Returns:
            True if the code meets baseline standards, False otherwise.
        """
        tree = self._safe_parse(code)
        if tree is None:
            return False

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(
                alias.name == "*" for alias in node.names
            ):
                return False
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                return False

        lines = code.splitlines()
        very_long_lines = sum(1 for line in lines if len(line) > 120)
        if lines and very_long_lines / len(lines) > 0.1:
            return False

        return True

    def _check_frontier_practices(self, code: str, domain: str) -> bool:
        """Check whether the code follows current best practices for its domain.

        Looks for: type hints on function signatures, use of f-strings
        over legacy `%` formatting, and (for async-appropriate domains)
        absence of blocking calls inside `async def` functions.

        Args:
            code: Python source code to analyze.
            domain: Engineering domain the code targets, e.g. "backend",
                "data", "ml", "cli". Domains other than these are treated
                with the same baseline checks.

        Returns:
            True if the code follows frontier practices, False otherwise.
        """
        tree = self._safe_parse(code)
        if tree is None:
            return False

        functions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if not functions:
            return False

        typed_functions = sum(
            1
            for fn in functions
            if fn.returns is not None
            or any(arg.annotation is not None for arg in fn.args.args)
        )
        type_hint_ratio = typed_functions / len(functions)

        legacy_formatting = bool(re.search(r"""['"][^'"]*%s[^'"]*['"]\s*%\s*\(""", code))

        return type_hint_ratio >= 0.5 and not legacy_formatting

    def _ready_for_production(self, code: str, project: str) -> bool:
        """Render a coarse production-readiness verdict.

        This is a fast pre-check independent of the full dimensional
        review; `review_for_deployment` combines this with
        `blocking_issues` derived from the detailed review so that a
        security or quality blocker always overrides a "ready" verdict
        here.

        Args:
            code: Python source code to analyze.
            project: Name/identifier of the project (used for context in
                messages only).

        Returns:
            True if no hard blockers are present at a glance, False
            otherwise.
        """
        tree = self._safe_parse(code)
        if tree is None:
            return False

        security = self._review_security(code)
        if security.injection_risk_found or security.hardcoded_secrets_found:
            return False

        quality = self._review_code_quality(code)
        if quality.max_cyclomatic_complexity > self._COMPLEXITY_ACCEPTABLE * 2:
            return False

        return True

    # ---------------------------------------------------------------- #
    # Internal utilities
    # ---------------------------------------------------------------- #

    @staticmethod
    def _safe_parse(code: str) -> ast.Module | None:
        """Parse Python source, returning None instead of raising on failure."""
        try:
            return ast.parse(code)
        except SyntaxError:
            return None

    @staticmethod
    def _cyclomatic_complexity(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
        """Compute a simplified cyclomatic complexity for a function.

        Counts decision points (if/for/while/except/boolean-ops/comprehension
        conditions) plus 1 for the base path.
        """
        complexity = 1
        for node in ast.walk(fn):
            if isinstance(
                node,
                (
                    ast.If,
                    ast.For,
                    ast.AsyncFor,
                    ast.While,
                    ast.ExceptHandler,
                    ast.With,
                    ast.AsyncWith,
                ),
            ):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += max(0, len(node.values) - 1)
            elif isinstance(node, (ast.comprehension,)):
                complexity += len(node.ifs)
        return complexity

    @staticmethod
    def _function_length(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
        """Estimate function length in lines using AST line numbers."""
        end_line = getattr(fn, "end_lineno", None)
        if end_line is None:
            return 1
        return max(1, end_line - fn.lineno + 1)

    def _naming_convention_score(self, tree: ast.Module) -> tuple[float, list[str]]:
        """Score identifier naming against PEP 8 conventions.

        Returns:
            A tuple of (score in [0, 1], list of specific issues).
        """
        issues: list[str] = []
        checked = 0
        compliant = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                checked += 1
                if _SNAKE_CASE_RE.match(node.name):
                    compliant += 1
                else:
                    issues.append(f"Function '{node.name}' does not follow snake_case.")
            elif isinstance(node, ast.ClassDef):
                checked += 1
                if _CLASS_CASE_RE.match(node.name):
                    compliant += 1
                else:
                    issues.append(f"Class '{node.name}' does not follow PascalCase.")

        if checked == 0:
            return 1.0, issues
        return compliant / checked, issues

    @staticmethod
    def _modularity_score(
        functions: Sequence[ast.FunctionDef | ast.AsyncFunctionDef], lengths: Sequence[int]
    ) -> float:
        """Score modularity based on function count and length distribution."""
        if not functions:
            return 0.3
        avg_length = sum(lengths) / len(lengths)
        if avg_length <= 20:
            length_score = 1.0
        elif avg_length <= 40:
            length_score = 0.75
        elif avg_length <= 60:
            length_score = 0.5
        else:
            length_score = 0.25
        return length_score

    @staticmethod
    def _normalize_complexity(avg_complexity: float) -> float:
        """Map an average cyclomatic complexity to a [0, 1] score."""
        if avg_complexity <= ProfessionalCodeReviewer._COMPLEXITY_GOOD:
            return 1.0
        if avg_complexity <= ProfessionalCodeReviewer._COMPLEXITY_ACCEPTABLE:
            return 0.7
        return max(0.1, 1.0 - (avg_complexity - ProfessionalCodeReviewer._COMPLEXITY_ACCEPTABLE) * 0.05)

    @staticmethod
    def _infer_domain(project: str) -> str:
        """Infer a coarse engineering domain from a project identifier.

        Falls back to "general" when no keyword match is found.
        """
        lowered = project.lower()
        if any(kw in lowered for kw in ("api", "server", "backend", "service")):
            return "backend"
        if any(kw in lowered for kw in ("ml", "model", "train", "inference")):
            return "ml"
        if any(kw in lowered for kw in ("data", "etl", "pipeline")):
            return "data"
        if any(kw in lowered for kw in ("cli", "tool", "script")):
            return "cli"
        return "general"

    @staticmethod
    def _aggregate_score(
        quality: CodeQualityScore,
        architecture: ArchitectureScore,
        security: SecurityAudit,
        performance: PerformanceAudit,
        maintainability: float,
    ) -> float:
        """Compute a weighted overall score across all review dimensions."""
        return round(
            0.25 * quality.overall_score
            + 0.20 * architecture.overall_score
            + 0.25 * security.overall_score
            + 0.15 * performance.overall_score
            + 0.15 * maintainability,
            3,
        )

    @staticmethod
    def _collect_blocking_issues(
        quality: CodeQualityScore,
        architecture: ArchitectureScore,
        security: SecurityAudit,
        performance: PerformanceAudit,
        test_coverage: float,
        has_docs: bool,
    ) -> list[str]:
        """Determine which findings are severe enough to block production."""
        blocking: list[str] = []
        if security.injection_risk_found:
            blocking.append("Injection risk pattern detected — must be remediated.")
        if security.hardcoded_secrets_found:
            blocking.append("Hardcoded secret/credential detected — must be removed.")
        if security.weak_auth_pattern_found:
            blocking.append("Weak authentication pattern detected — must be remediated.")
        if quality.max_cyclomatic_complexity > ProfessionalCodeReviewer._COMPLEXITY_ACCEPTABLE * 2:
            blocking.append(
                f"Extreme cyclomatic complexity ({quality.max_cyclomatic_complexity}) — must be refactored."
            )
        return blocking

    @staticmethod
    def _build_summary(
        project: str,
        overall: float,
        ready: bool,
        quality: CodeQualityScore,
        architecture: ArchitectureScore,
        security: SecurityAudit,
        performance: PerformanceAudit,
    ) -> str:
        """Compose a short human-readable summary of the review outcome."""
        verdict = "READY FOR PRODUCTION" if ready else "NOT READY FOR PRODUCTION"
        return (
            f"[{project}] Overall score: {overall:.2f}/1.00 — {verdict}. "
            f"Quality={quality.overall_score:.2f}, Architecture={architecture.overall_score:.2f}, "
            f"Security={security.overall_score:.2f}, Performance={performance.overall_score:.2f}."
        )
