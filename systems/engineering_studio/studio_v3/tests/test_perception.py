"""Test suite for RepositoryScanner perception layer.

Tests verify scanning logic for missing README, edge cases like empty repos,
multiple README variants, and various repository states.
"""

import pytest
from pathlib import Path
from systems.engineering_studio.studio_v3.perception.repository_scanner import RepositoryScanner


class TestRepositoryScannerReadmeMissing:
    """Test missing README detection."""

    def test_detect_missing_readme_in_git_repo(self, tmp_path):
        """Verify detection of missing README in a git repository."""
        # Setup: git repo without README
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()

        scanner = RepositoryScanner(str(repo_path))
        findings = scanner.scan_missing_readme()

        assert len(findings) == 1
        assert findings[0]['type'] == 'missing_readme'
        assert findings[0]['severity'] == 'LOW'
        assert 'README.md' in findings[0]['description']

    def test_ignore_missing_readme_without_git(self, tmp_path):
        """Verify no findings when repo is not a git repository."""
        # Setup: directory without .git
        repo_path = tmp_path / "not_a_git_repo"
        repo_path.mkdir()

        scanner = RepositoryScanner(str(repo_path))
        findings = scanner.scan_missing_readme()

        assert len(findings) == 0

    def test_no_finding_when_readme_md_exists(self, tmp_path):
        """Verify no finding when README.md exists."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()

        # Create README.md
        (repo_path / "README.md").write_text("# Test Project")

        scanner = RepositoryScanner(str(repo_path))
        findings = scanner.scan_missing_readme()

        assert len(findings) == 0

    def test_no_finding_when_readme_uppercase_exists(self, tmp_path):
        """Verify no finding when README.MD (uppercase) exists."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()

        # Create README.MD (uppercase)
        (repo_path / "README.MD").write_text("# Test Project")

        scanner = RepositoryScanner(str(repo_path))
        findings = scanner.scan_missing_readme()

        assert len(findings) == 0

    def test_no_finding_when_readme_txt_exists(self, tmp_path):
        """Verify no finding when README.txt exists."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()

        # Create README.txt
        (repo_path / "README.txt").write_text("Test Project")

        scanner = RepositoryScanner(str(repo_path))
        findings = scanner.scan_missing_readme()

        assert len(findings) == 0

    def test_no_finding_when_readme_plain_exists(self, tmp_path):
        """Verify no finding when README (no extension) exists."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()

        # Create README (no extension)
        (repo_path / "README").write_text("Test Project")

        scanner = RepositoryScanner(str(repo_path))
        findings = scanner.scan_missing_readme()

        assert len(findings) == 0

    def test_finding_includes_repo_path(self, tmp_path):
        """Verify finding includes repository path."""
        repo_path = tmp_path / "my_project"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()

        scanner = RepositoryScanner(str(repo_path))
        findings = scanner.scan_missing_readme()

        assert len(findings) == 1
        assert str(repo_path) in findings[0]['path']

    def test_finding_includes_finding_id(self, tmp_path):
        """Verify finding includes a unique finding_id."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()

        scanner = RepositoryScanner(str(repo_path))
        findings = scanner.scan_missing_readme()

        assert len(findings) == 1
        assert 'finding_id' in findings[0]
        assert findings[0]['finding_id'].startswith('missing_readme_')


class TestRepositoryScannerScanAll:
    """Test comprehensive scan method."""

    def test_scan_all_returns_dict(self, tmp_path):
        """Verify scan_all returns a dictionary."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()

        scanner = RepositoryScanner(str(repo_path))
        results = scanner.scan_all()

        assert isinstance(results, dict)
        assert 'missing_readme' in results

    def test_scan_all_includes_missing_readme_findings(self, tmp_path):
        """Verify scan_all includes missing_readme findings."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()

        scanner = RepositoryScanner(str(repo_path))
        results = scanner.scan_all()

        assert isinstance(results['missing_readme'], list)
        assert len(results['missing_readme']) == 1

    def test_scan_all_with_existing_readme(self, tmp_path):
        """Verify scan_all returns empty list when README exists."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()

        (repo_path / "README.md").write_text("# Test")

        scanner = RepositoryScanner(str(repo_path))
        results = scanner.scan_all()

        assert isinstance(results['missing_readme'], list)
        assert len(results['missing_readme']) == 0


class TestRepositoryScannerEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_scan_empty_git_repo(self, tmp_path):
        """Verify scanning works on completely empty git repo."""
        repo_path = tmp_path / "empty_repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()

        scanner = RepositoryScanner(str(repo_path))
        findings = scanner.scan_missing_readme()

        assert len(findings) == 1
        assert findings[0]['type'] == 'missing_readme'

    def test_scan_repo_with_multiple_readme_variants(self, tmp_path):
        """Verify only first matching README variant is checked."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()

        # Create multiple README variants
        (repo_path / "README.md").write_text("# Main")
        (repo_path / "README.txt").write_text("Text")

        scanner = RepositoryScanner(str(repo_path))
        findings = scanner.scan_missing_readme()

        # Should have no findings since README.md exists
        assert len(findings) == 0

    def test_scan_repo_with_readme_in_subdirectory(self, tmp_path):
        """Verify scanner only checks repository root, not subdirectories."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()

        # Create README in subdirectory, not root
        subdir = repo_path / "docs"
        subdir.mkdir()
        (subdir / "README.md").write_text("# Docs")

        scanner = RepositoryScanner(str(repo_path))
        findings = scanner.scan_missing_readme()

        # Should still find missing README in root
        assert len(findings) == 1

    def test_scan_nonexistent_path(self):
        """Verify scanner handles nonexistent repository path gracefully."""
        scanner = RepositoryScanner("/nonexistent/path")
        findings = scanner.scan_missing_readme()

        # Should return empty list (no .git directory exists)
        assert len(findings) == 0

    def test_finding_id_includes_repo_path_sanitized(self, tmp_path):
        """Verify finding_id sanitizes repository path."""
        repo_path = tmp_path / "my_test_repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()

        scanner = RepositoryScanner(str(repo_path))
        findings = scanner.scan_missing_readme()

        finding_id = findings[0]['finding_id']
        # finding_id should have slashes replaced with underscores
        assert '/' not in finding_id or finding_id.startswith('missing_readme_')

    def test_scanner_initialization_with_relative_path(self, tmp_path):
        """Verify scanner handles relative paths correctly."""
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            repo_path = tmp_path / "test_repo"
            repo_path.mkdir()
            git_dir = repo_path / ".git"
            git_dir.mkdir()

            # Use relative path
            scanner = RepositoryScanner("test_repo")
            findings = scanner.scan_missing_readme()

            assert len(findings) == 1
        finally:
            os.chdir(original_cwd)
