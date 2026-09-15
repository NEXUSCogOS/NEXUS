"""Shared fixtures for Librarian's own test suite."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

REAL_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
FEDERATION_ROOT = Path(__file__).resolve().parents[2] / "nexus_federation"
DAT_AI_ROOT = Path(__file__).resolve().parents[2] / "dat_ai"

# Librarian's contract tests intentionally exercise the shared federation
# packages directly.  Make that sibling system importable when tests are run
# from Librarian's own root, matching the deployed multi-system layout.
if str(FEDERATION_ROOT) not in sys.path:
    sys.path.insert(0, str(FEDERATION_ROOT))
if str(DAT_AI_ROOT) not in sys.path:
    sys.path.insert(0, str(DAT_AI_ROOT))


@pytest.fixture
def real_data_dir():
    """The real, historical ingested corpus (93 sources / 297 documents),
    read-only for tests -- never mutated in place."""
    return REAL_DATA_DIR


@pytest.fixture
def isolated_data_dir(tmp_path):
    """A throwaway COPY of the real corpus data, safe to mutate."""
    dest = tmp_path / "data"
    shutil.copytree(REAL_DATA_DIR, dest)
    return dest
