from pathlib import Path
from typing import List, Dict, Any

class RepositoryScanner:
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    def scan_missing_readme(self) -> List[Dict[str, Any]]:
        """
        Scan repository for missing README.md
        Returns list of findings (empty if README exists)
        """
        findings = []

        readme_variants = ['README.md', 'README.MD', 'README.txt', 'README']
        has_readme = any((self.repo_path / variant).exists() for variant in readme_variants)

        if not has_readme and (self.repo_path / '.git').exists():
            findings.append({
                'type': 'missing_readme',
                'path': str(self.repo_path),
                'severity': 'LOW',
                'description': 'Repository missing README.md documentation',
                'finding_id': 'missing_readme_' + str(self.repo_path).replace('/', '_')
            })

        return findings

    def scan_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """Run all perception checks"""
        return {
            'missing_readme': self.scan_missing_readme(),
        }
