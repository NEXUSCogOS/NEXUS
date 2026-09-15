from pathlib import Path

class PatchGenerator:
    @staticmethod
    def generate_readme(repo_path: str) -> str:
        """
        Generate minimal README.md for repository
        Returns path to created file
        """
        repo_path = Path(repo_path)
        readme_path = repo_path / 'README.md'

        project_name = repo_path.name

        content = f"""# {project_name}

This is an automatically generated README placeholder.

## Getting Started

To build and run this project:

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest
```

## Project Structure

- `src/` - Source code
- `tests/` - Test files
- `docs/` - Documentation

## License

See LICENSE file for details.
"""

        readme_path.write_text(content)
        return str(readme_path)
