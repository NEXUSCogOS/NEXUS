"""Fail-closed safety gate for autonomous Git promotion.

This gate exists because an Engineering Studio commit previously promoted a
large pre-existing staged-deletion state that was outside the intended mission.

The gate never commits, stages, restores, resets, or deletes anything.
It only observes repository/index state and returns an allow/deny decision.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable
import json
import subprocess


@dataclass(frozen=True)
class PromotionDecision:
    allowed: bool
    reasons: list[str]
    staged_paths: list[str]
    staged_deletions: list[str]
    tracked_count: int
    baseline_tracked_count: int
    tracked_drop_fraction: float

    def to_dict(self) -> dict:
        return asdict(self)


class AutonomousGitPromotionGate:
    """Mission-specific fail-closed Git promotion validator."""

    MAX_TRACKED_DROP_FRACTION = 0.05

    def __init__(self, repo_path: str | Path):
        self.repo = Path(repo_path).resolve()

    def _git(self, *args: str) -> str:
        proc = subprocess.run(
            ["git", *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(args)} failed ({proc.returncode}): "
                f"{proc.stderr.strip()}"
            )
        return proc.stdout

    def _lines(self, *args: str) -> list[str]:
        return [x for x in self._git(*args).splitlines() if x.strip()]

    def evaluate(
        self,
        *,
        allowed_paths: Iterable[str],
        baseline_tracked_count: int,
        allowed_deletions: Iterable[str] = (),
        require_clean_preexisting_index: bool = False,
    ) -> PromotionDecision:
        allowed = set(allowed_paths)
        allowed_delete = set(allowed_deletions)

        staged = self._lines("diff", "--cached", "--name-only")
        deletions = self._lines(
            "diff", "--cached", "--diff-filter=D", "--name-only"
        )
        tracked = len(self._lines("ls-files"))

        reasons: list[str] = []

        unexpected = sorted(set(staged) - allowed)
        if unexpected:
            reasons.append(
                "staged paths outside mission allowlist: "
                + ", ".join(unexpected[:20])
            )

        unexpected_deletions = sorted(set(deletions) - allowed_delete)
        if unexpected_deletions:
            reasons.append(
                "unapproved staged deletions: "
                + ", ".join(unexpected_deletions[:20])
            )

        if baseline_tracked_count <= 0:
            reasons.append("invalid baseline tracked-file count")
            drop_fraction = 1.0
        else:
            drop_fraction = max(
                0.0,
                (baseline_tracked_count - tracked) / baseline_tracked_count,
            )

        if drop_fraction > self.MAX_TRACKED_DROP_FRACTION:
            reasons.append(
                f"tracked-file count dropped {drop_fraction:.2%}; "
                f"maximum permitted is {self.MAX_TRACKED_DROP_FRACTION:.2%}"
            )

        if ".gitignore" in deletions:
            reasons.append(".gitignore removal is forbidden")

        if require_clean_preexisting_index and staged:
            reasons.append(
                "index was required to be clean before mission staging"
            )

        return PromotionDecision(
            allowed=not reasons,
            reasons=reasons,
            staged_paths=staged,
            staged_deletions=deletions,
            tracked_count=tracked,
            baseline_tracked_count=baseline_tracked_count,
            tracked_drop_fraction=drop_fraction,
        )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--baseline-tracked-count", type=int, required=True)
    parser.add_argument("--allow", action="append", default=[])
    parser.add_argument("--allow-delete", action="append", default=[])
    args = parser.parse_args()

    gate = AutonomousGitPromotionGate(args.repo)
    decision = gate.evaluate(
        allowed_paths=args.allow,
        baseline_tracked_count=args.baseline_tracked_count,
        allowed_deletions=args.allow_delete,
    )

    print(json.dumps(decision.to_dict(), indent=2))
    return 0 if decision.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
