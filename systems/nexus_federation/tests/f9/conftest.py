"""Fixtures for F9 executive coordinator tests.

F9 tests do not depend on DAT.AI/institutional contracts.
They test the coordinator in isolation with a temporary FederationStore.
"""

import pytest
import tempfile
from pathlib import Path

from executive import ExecutiveCoordinator
from persistence.db import FederationStore


@pytest.fixture
def temp_store():
    """Temporary FederationStore for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FederationStore(Path(tmpdir) / "test.db")
        yield store


@pytest.fixture
def coordinator(temp_store):
    """ExecutiveCoordinator with temporary store."""
    return ExecutiveCoordinator(temp_store)
