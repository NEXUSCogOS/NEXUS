"""Tests for the baseline academic assessment report generator.

Runs against the real repository (real execution log, real
.directives-ingestion, real git history) but always writes the generated
Markdown report to a temp path, never the real research/ deliverable path.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from observatory.baseline_assessment import generate_baseline_report

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_generate_baseline_report_runs_and_returns_expected_keys(tmp_path):
    output_path = tmp_path / "baseline_assessment.md"

    result = generate_baseline_report(repo_path=REPO_ROOT, output_path=output_path)

    for key in (
        "directive_backlog",
        "execution_log_audit",
        "storage_sizes",
        "commit_count",
        "python_file_count",
    ):
        assert key in result


def test_generate_baseline_report_writes_markdown_with_evidence_column(tmp_path):
    output_path = tmp_path / "baseline_assessment.md"

    generate_baseline_report(repo_path=REPO_ROOT, output_path=output_path)

    assert output_path.exists()
    content = output_path.read_text()
    assert "Evidence (this report)" in content
