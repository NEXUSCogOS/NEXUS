"""Shared pytest fixtures.

Unit tests must run with no network, no database and no credentials. Anything
requiring those is marked and skipped when unavailable — never silently passed.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

DAT_AI_ROOT = Path(__file__).resolve().parent.parent
BACKEND = DAT_AI_ROOT / "backend"

# Make `app` importable without requiring PYTHONPATH gymnastics from the caller.
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Tests declare their own runtime mode before app.config is first imported.
os.environ.setdefault("DAT_AI_RUNTIME_MODE", "test")


@pytest.fixture(scope="session")
def dat_ai_root() -> Path:
    return DAT_AI_ROOT


@pytest.fixture(scope="session")
def aoi_config_path(dat_ai_root: Path) -> Path:
    return dat_ai_root / "configs" / "aoi" / "dong_nai.geojson"


@pytest.fixture(scope="session")
def dong_nai_aoi(aoi_config_path: Path):
    from app.satellite.aoi import load_aoi

    return load_aoi(aoi_config_path, "dong_nai")


@pytest.fixture(scope="session")
def stac_fixture() -> dict:
    """A recorded CDSE STAC response — the real commissioning specimen.

    Captured from https://stac.dataspace.copernicus.eu/v1/search on
    2026-08-14. Used so parsing tests need no network.
    """
    path = Path(__file__).parent / "fixtures" / "stac_response.json"
    return json.loads(path.read_text())


@pytest.fixture
def test_settings(tmp_path: Path):
    """Settings pinned to the test runtime mode with a temporary cache."""
    from app.config import RuntimeMode, Settings

    from dataclasses import replace

    from app.config import load_settings

    base = load_settings()
    return replace(
        base,
        runtime_mode=RuntimeMode.TEST,
        satellite_cache_dir=tmp_path / "cache",
        log_dir=tmp_path / "logs",
    )


# ---------------------------------------------------------------------
# database availability
# ---------------------------------------------------------------------


def _database_available() -> bool:
    try:
        from sqlalchemy import create_engine, text

        url = os.getenv(
            "TEST_DATABASE_URL",
            os.getenv("DATABASE_URL", "postgresql://datai:datai@localhost:5432/datai"),
        )
        engine = create_engine(url, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


DATABASE_AVAILABLE = _database_available()

requires_database = pytest.mark.skipif(
    not DATABASE_AVAILABLE,
    reason="No PostGIS database reachable (set TEST_DATABASE_URL)",
)


@pytest.fixture(scope="session")
def db_engine():
    if not DATABASE_AVAILABLE:
        pytest.skip("database unavailable")
    from sqlalchemy import create_engine

    url = os.getenv(
        "TEST_DATABASE_URL",
        os.getenv("DATABASE_URL", "postgresql://datai:datai@localhost:5432/datai"),
    )
    return create_engine(url)


@pytest.fixture
def db_session(db_engine):
    """A session whose work is always rolled back."""
    from sqlalchemy.orm import sessionmaker

    connection = db_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def api_client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client


# ---------------------------------------------------------------------
# credential availability
# ---------------------------------------------------------------------


def _has_cdse_credentials() -> bool:
    return bool(
        (os.getenv("CDSE_S3_ACCESS_KEY") and os.getenv("CDSE_S3_SECRET_KEY"))
        or (os.getenv("CDSE_USERNAME") and os.getenv("CDSE_PASSWORD"))
    )


requires_cdse_credentials = pytest.mark.skipif(
    not _has_cdse_credentials(),
    reason=(
        "No CDSE credentials. Set CDSE_S3_ACCESS_KEY/CDSE_S3_SECRET_KEY or "
        "CDSE_USERNAME/CDSE_PASSWORD to run commissioning tests."
    ),
)

requires_network = pytest.mark.skipif(
    os.getenv("DAT_AI_OFFLINE_TESTS", "").lower() in {"1", "true", "yes"},
    reason="DAT_AI_OFFLINE_TESTS is set",
)


@pytest.fixture
def synthetic_reflectance():
    """Deterministic, clearly-labelled fake reflectance for plumbing tests.

    This is a TEST fixture. It is never reachable from a production path — see
    tests/unit/test_no_synthetic_in_production.py which enforces that.
    """
    import numpy as np

    height = width = 256
    ramp = np.linspace(0.0, 1.0, height * width, dtype=np.float32).reshape(
        height, width
    )
    return np.stack([ramp, ramp * 0.5, ramp * 0.25, ramp * 0.75])
