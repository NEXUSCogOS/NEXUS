"""Tests for professional_auditor.py.

Covers dataclass construction, individual audit dimensions, score
aggregation/sign-off logic, and an end-to-end integration audit against a
generated sample project.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from systems.engineering_studio.studio_v3.quality.professional_auditor import (
    ArchitectureAudit,
    AuditReport,
    CodeQualityAudit,
    ComplianceAudit,
    DocumentationAudit,
    PerformanceAudit,
    ProfessionalAuditor,
    SecurityAudit,
    TestingAudit,
)


def _make_perfect_dimensions() -> dict[str, object]:
    """Build a set of audit dimension objects representing a flawless project."""
    return {
        "code_quality": CodeQualityAudit(
            files_analyzed=5,
            total_lines=500,
            average_function_length=10.0,
            long_functions=(),
            complexity_violations=(),
            naming_violations=(),
            duplicate_code_blocks=0,
            lint_findings=(),
            score=100.0,
            findings=("No significant code-quality issues detected.",),
        ),
        "architecture": ArchitectureAudit(
            modules_analyzed=5,
            circular_dependencies=(),
            layering_violations=(),
            god_modules=(),
            coupling_score=1.0,
            cohesion_score=95.0,
            score=100.0,
            findings=("No significant architectural issues detected.",),
        ),
        "performance": PerformanceAudit(
            files_analyzed=5,
            nested_loop_hotspots=(),
            blocking_io_in_hot_paths=(),
            inefficient_patterns=(),
            large_object_allocations=(),
            score=100.0,
            findings=("No significant performance risks detected.",),
        ),
        "security": SecurityAudit(
            files_analyzed=5,
            hardcoded_secrets=(),
            injection_risks=(),
            insecure_deserialization=(),
            weak_crypto=(),
            unsafe_permissions=(),
            critical_findings=0,
            high_findings=0,
            score=100.0,
            findings=("No security issues detected by static analysis.",),
        ),
        "compliance": ComplianceAudit(
            license_present=True,
            readme_present=True,
            changelog_present=True,
            contributing_guide_present=True,
            code_of_conduct_present=True,
            required_files_missing=(),
            policy_violations=(),
            score=100.0,
            findings=("All core governance files present.",),
        ),
        "testing": TestingAudit(
            source_files=5,
            test_files=5,
            test_functions=20,
            estimated_coverage_pct=100.0,
            untested_modules=(),
            meets_coverage_gate=True,
            score=100.0,
            findings=("Estimated module-level test coverage: 100.0%",),
        ),
        "documentation": DocumentationAudit(
            public_symbols=20,
            documented_symbols=20,
            documentation_coverage_pct=100.0,
            undocumented_symbols=(),
            meets_documentation_gate=True,
            score=100.0,
            findings=("Documentation coverage: 100.0% (20/20)",),
        ),
    }


class TestAuditReportCreation:
    """Tests that AuditReport and its component dataclasses construct correctly."""

    def test_audit_report_construction(self) -> None:
        dims = _make_perfect_dimensions()
        report = AuditReport(
            project_path="/tmp/example",
            code_quality_audit=dims["code_quality"],
            architectural_audit=dims["architecture"],
            performance_audit=dims["performance"],
            security_audit=dims["security"],
            compliance_audit=dims["compliance"],
            testing_audit=dims["testing"],
            documentation_audit=dims["documentation"],
            deployment_readiness=True,
            production_readiness_score=100.0,
            recommendations=("No blocking issues found; project meets production-readiness gates.",),
            sign_off="APPROVED",
        )
        assert report.project_path == "/tmp/example"
        assert report.sign_off == "APPROVED"
        assert report.deployment_readiness is True
        assert report.production_readiness_score == 100.0

    def test_dataclasses_are_frozen(self) -> None:
        dims = _make_perfect_dimensions()
        with pytest.raises(Exception):
            dims["code_quality"].score = 0.0  # type: ignore[misc]


class TestScoringAndReadiness:
    """Tests for the auditor's scoring, recommendation, and sign-off logic."""

    def test_calculate_readiness_score_perfect_project(self) -> None:
        auditor = ProfessionalAuditor()
        dims = _make_perfect_dimensions()
        score = auditor._calculate_readiness_score(**dims)
        assert score == 100.0

    def test_sign_off_approved_when_all_gates_pass(self) -> None:
        auditor = ProfessionalAuditor()
        dims = _make_perfect_dimensions()
        sign_off = auditor._generate_sign_off(
            score=100.0,
            security=dims["security"],
            testing=dims["testing"],
            documentation=dims["documentation"],
            deployment_ready=True,
        )
        assert sign_off == "APPROVED"

    def test_sign_off_needs_work_on_critical_security_finding(self) -> None:
        auditor = ProfessionalAuditor()
        dims = _make_perfect_dimensions()
        bad_security = SecurityAudit(
            files_analyzed=5,
            hardcoded_secrets=("app.py:10",),
            injection_risks=(),
            insecure_deserialization=(),
            weak_crypto=(),
            unsafe_permissions=(),
            critical_findings=1,
            high_findings=0,
            score=85.0,
            findings=("1 hardcoded secret(s) detected",),
        )
        sign_off = auditor._generate_sign_off(
            score=95.0,
            security=bad_security,
            testing=dims["testing"],
            documentation=dims["documentation"],
            deployment_ready=True,
        )
        assert sign_off == "NEEDS_WORK"

    def test_sign_off_needs_work_below_coverage_gate(self) -> None:
        auditor = ProfessionalAuditor()
        dims = _make_perfect_dimensions()
        low_coverage = TestingAudit(
            source_files=5,
            test_files=1,
            test_functions=2,
            estimated_coverage_pct=50.0,
            untested_modules=("mod_a", "mod_b"),
            meets_coverage_gate=False,
            score=50.0,
            findings=("Estimated module-level test coverage: 50.0%",),
        )
        sign_off = auditor._generate_sign_off(
            score=92.0,
            security=dims["security"],
            testing=low_coverage,
            documentation=dims["documentation"],
            deployment_ready=True,
        )
        assert sign_off == "NEEDS_WORK"

    def test_generate_recommendations_flags_critical_security(self) -> None:
        auditor = ProfessionalAuditor()
        dims = _make_perfect_dimensions()
        bad_security = SecurityAudit(
            files_analyzed=5,
            hardcoded_secrets=("app.py:10",),
            injection_risks=(),
            insecure_deserialization=(),
            weak_crypto=(),
            unsafe_permissions=(),
            critical_findings=1,
            high_findings=0,
            score=85.0,
            findings=("1 hardcoded secret(s) detected",),
        )
        dims["security"] = bad_security
        recs = auditor._generate_recommendations(**dims)
        assert any("CRITICAL" in r for r in recs)

    def test_generate_recommendations_clean_project(self) -> None:
        auditor = ProfessionalAuditor()
        dims = _make_perfect_dimensions()
        recs = auditor._generate_recommendations(**dims)
        assert len(recs) == 1
        assert "No blocking issues" in recs[0]


class TestIntegrationAuditSampleProject:
    """End-to-end integration test: audit a small generated sample project."""

    @pytest.fixture()
    def sample_project(self, tmp_path: Path) -> Path:
        project = tmp_path / "sample_project"
        project.mkdir()

        (project / "README.md").write_text("# Sample Project\n\nA sample.\n")
        (project / "LICENSE").write_text("MIT License\n")

        (project / "calculator.py").write_text(
            textwrap.dedent(
                '''
                """A small calculator module used for the integration test."""


                def add(a: int, b: int) -> int:
                    """Return the sum of two integers."""
                    return a + b


                def subtract(a: int, b: int) -> int:
                    """Return the difference of two integers."""
                    return a - b
                '''
            )
        )

        (project / "test_calculator.py").write_text(
            textwrap.dedent(
                '''
                """Tests for calculator.py."""

                from calculator import add, subtract


                def test_add() -> None:
                    """add() should sum two integers."""
                    assert add(2, 3) == 5


                def test_subtract() -> None:
                    """subtract() should difference two integers."""
                    assert subtract(5, 3) == 2
                '''
            )
        )

        return project

    def test_audit_system_runs_end_to_end(self, sample_project: Path) -> None:
        auditor = ProfessionalAuditor()
        report = auditor.audit_system(str(sample_project))

        assert isinstance(report, AuditReport)
        assert report.project_path == str(sample_project)
        assert 0.0 <= report.production_readiness_score <= 100.0
        assert report.sign_off in ("APPROVED", "NEEDS_WORK")
        assert report.code_quality_audit.files_analyzed >= 2
        assert report.testing_audit.test_files == 1
        assert report.compliance_audit.license_present is True
        assert report.compliance_audit.readme_present is True
        assert len(report.recommendations) >= 1

    def test_audit_system_raises_for_missing_path(self, tmp_path: Path) -> None:
        auditor = ProfessionalAuditor()
        missing = tmp_path / "does_not_exist"
        with pytest.raises(FileNotFoundError):
            auditor.audit_system(str(missing))

    def test_audit_system_raises_for_file_path(self, tmp_path: Path) -> None:
        auditor = ProfessionalAuditor()
        file_path = tmp_path / "not_a_dir.py"
        file_path.write_text("x = 1\n")
        with pytest.raises(NotADirectoryError):
            auditor.audit_system(str(file_path))

    def test_audit_security_detects_hardcoded_secret(self, tmp_path: Path) -> None:
        project = tmp_path / "insecure_project"
        project.mkdir()
        (project / "config.py").write_text(
            'api_key = "synthetic_test_api_key_value"\n'
        )
        (project / "test_config.py").write_text("def test_placeholder() -> None:\n    assert True\n")

        auditor = ProfessionalAuditor()
        security = auditor._audit_security(str(project))
        assert security.critical_findings >= 1
        assert len(security.hardcoded_secrets) >= 1

    def test_audit_documentation_detects_missing_docstrings(self, tmp_path: Path) -> None:
        project = tmp_path / "undocumented_project"
        project.mkdir()
        (project / "mod.py").write_text("def public_func(x):\n    return x\n")

        auditor = ProfessionalAuditor()
        documentation = auditor._audit_documentation(str(project))
        assert documentation.documentation_coverage_pct < 100.0
        assert documentation.meets_documentation_gate is False
