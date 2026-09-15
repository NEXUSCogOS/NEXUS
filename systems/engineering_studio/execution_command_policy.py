"""Fail-closed execution policy for the public NEXUS research release."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

_ALLOWED_EXECUTABLES = {
    "python",
    "python3",
    "pytest",
}

_FORBIDDEN_ARGUMENT_FRAGMENTS = (
    ";",
    "&&",
    "||",
    "|",
    "`",
    "$(",
    "\n",
    "\r",
    "\x00",
)

_ALLOWED_PYTHON_MODULES = {
    "pytest",
}


class ExecutionPolicyError(ValueError):
    """Raised when an execution request crosses the public-release boundary."""


def validate_test_command(command: Sequence[str]) -> list[str]:
    if isinstance(command, (str, bytes)):
        raise ExecutionPolicyError("command must be argv, never a shell string")

    argv = [str(x) for x in command]

    if not argv:
        raise ExecutionPolicyError("empty command")

    executable = Path(argv[0]).name

    if executable not in _ALLOWED_EXECUTABLES:
        raise ExecutionPolicyError(
            f"executable not permitted by public research policy: {executable}"
        )

    for arg in argv:
        if any(fragment in arg for fragment in _FORBIDDEN_ARGUMENT_FRAGMENTS):
            raise ExecutionPolicyError("shell/control syntax prohibited")

    if executable in {"python", "python3"}:
        if len(argv) < 3 or argv[1] != "-m":
            raise ExecutionPolicyError(
                "Python execution restricted to approved -m modules"
            )

        if argv[2] not in _ALLOWED_PYTHON_MODULES:
            raise ExecutionPolicyError(
                f"Python module not permitted: {argv[2]}"
            )

    return argv
