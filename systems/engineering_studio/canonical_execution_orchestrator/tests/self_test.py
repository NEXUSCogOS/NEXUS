from pathlib import Path
import json
import subprocess
import sys

root = Path.home() / "NEXUS"

target = (
    root /
    "systems" /
    "engineering_studio" /
    "canonical_execution_orchestrator"
)

required = [
    target / "controller.py",
    target / "status.sh",
    target / "config" / "programme.json",
    target / "human_returns" / "README.md",
]

for p in required:
    assert p.exists(), p

config = json.loads(
    (target / "config" / "programme.json").read_text()
)

assert config["automatic_registry_edit"] is False
assert config["automatic_human_attestation"] is False
assert config["automatic_github_publication"] is False

result = subprocess.run(
    [str(target / "status.sh")],
    capture_output=True,
    text=True,
)

assert result.returncode == 0, (
    result.stdout + result.stderr
)

assert "HUMAN_REVIEW_PENDING" in result.stdout

print("PASS: canonical orchestrator self-test")
