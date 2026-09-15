"""Regression tests for autonomous Git promotion safety."""

from pathlib import Path
import subprocess

from systems.engineering_studio.governance.autonomous_git_promotion_gate import (
    AutonomousGitPromotionGate,
)


def _git(repo: Path, *args: str):
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "gate-test@nexus.local")
    _git(repo, "config", "user.name", "Gate Test")

    (repo / ".gitignore").write_text("*.tmp\n")
    (repo / "a.txt").write_text("a\n")
    (repo / "b.txt").write_text("b\n")
    _git(repo, "add", ".gitignore", "a.txt", "b.txt")
    _git(repo, "commit", "-m", "baseline")
    return repo


def test_gate_allows_exact_mission_allowlist(tmp_path):
    repo = _repo(tmp_path)
    (repo / "a.txt").write_text("changed\n")
    _git(repo, "add", "a.txt")

    gate = AutonomousGitPromotionGate(repo)
    decision = gate.evaluate(
        allowed_paths=["a.txt"],
        baseline_tracked_count=3,
    )

    assert decision.allowed is True
    assert decision.reasons == []


def test_gate_denies_preexisting_unexpected_staged_path(tmp_path):
    repo = _repo(tmp_path)
    (repo / "a.txt").write_text("mission\n")
    (repo / "b.txt").write_text("unrelated\n")
    _git(repo, "add", "a.txt", "b.txt")

    gate = AutonomousGitPromotionGate(repo)
    decision = gate.evaluate(
        allowed_paths=["a.txt"],
        baseline_tracked_count=3,
    )

    assert decision.allowed is False
    assert any(
        "outside mission allowlist" in reason
        for reason in decision.reasons
    )


def test_gate_denies_unapproved_deletion(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "rm", "b.txt")

    gate = AutonomousGitPromotionGate(repo)
    decision = gate.evaluate(
        allowed_paths=["b.txt"],
        baseline_tracked_count=3,
        allowed_deletions=[],
    )

    assert decision.allowed is False
    assert any(
        "unapproved staged deletions" in reason
        for reason in decision.reasons
    )


def test_gate_denies_gitignore_deletion_even_if_path_allowlisted(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "rm", ".gitignore")

    gate = AutonomousGitPromotionGate(repo)
    decision = gate.evaluate(
        allowed_paths=[".gitignore"],
        allowed_deletions=[".gitignore"],
        baseline_tracked_count=3,
    )

    assert decision.allowed is False
    assert ".gitignore removal is forbidden" in decision.reasons


def test_gate_denies_major_tracked_count_collapse(tmp_path):
    repo = _repo(tmp_path)

    gate = AutonomousGitPromotionGate(repo)

    # Simulate a historical baseline much larger than current tracked state.
    decision = gate.evaluate(
        allowed_paths=[],
        baseline_tracked_count=100,
    )

    assert decision.allowed is False
    assert any(
        "tracked-file count dropped" in reason
        for reason in decision.reasons
    )
