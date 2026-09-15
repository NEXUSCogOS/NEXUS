import subprocess
from pathlib import Path

class SandboxManager:
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    def create_branch(self, branch_name: str) -> str:
        """
        Create isolated git branch for repair
        Returns branch SHA after creation
        """
        subprocess.run(
            ['git', '-C', str(self.repo_path), 'checkout', 'main'],
            check=True, capture_output=True
        )
        subprocess.run(
            ['git', '-C', str(self.repo_path), 'pull', 'origin', 'main'],
            capture_output=True
        )

        subprocess.run(
            ['git', '-C', str(self.repo_path), 'checkout', '-b', branch_name],
            capture_output=True, text=True, check=True
        )

        sha = subprocess.run(
            ['git', '-C', str(self.repo_path), 'rev-parse', 'HEAD'],
            capture_output=True, text=True, check=True
        ).stdout.strip()

        return sha

    def rollback_branch(self, branch_name: str) -> None:
        """Delete repair branch on failure"""
        subprocess.run(
            ['git', '-C', str(self.repo_path), 'checkout', 'main'],
            capture_output=True
        )
        subprocess.run(
            ['git', '-C', str(self.repo_path), 'branch', '-D', branch_name],
            capture_output=True
        )
