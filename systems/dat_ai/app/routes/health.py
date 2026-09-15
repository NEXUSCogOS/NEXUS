"""Health, readiness and liveness endpoints.

The previous ``/health`` returned::

    {"status": "ok", "service": "dat.ai", "satellite_agent": "active"}

``satellite_agent: active`` was a constant string. It was returned identically
whether ingestion was configured, credentialed, commissioned or completely
absent — which is exactly the kind of claim that turns a dashboard green while
nothing works.

These endpoints report reality, computed at request time:

    /health      cheap process check, always 200 if the process is up
    /liveness    process is alive (no dependencies touched)
    /readiness   ready to serve real traffic; 503 when it is not
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.config import RuntimeMode, settings
from app.db import engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

ComponentState = Literal[
    "healthy", "degraded", "unhealthy", "unconfigured", "not_promoted", "disabled"
]


class ComponentHealth(BaseModel):
    state: ComponentState
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "unhealthy"]
    service: str = "dat.ai"
    runtime_mode: str
    timestamp: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    runtime_mode: str
    timestamp: str
    database: ComponentHealth
    postgis: ComponentHealth
    migrations: ComponentHealth
    classifier: ComponentHealth
    satellite_ingestion: ComponentHealth
    satellite_scheduler: ComponentHealth
    planet_validation: ComponentHealth
    configuration: ComponentHealth
    last_successful_ingestion: str | None = None
    last_pipeline_run: dict[str, Any] | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    problems: list[str] = Field(default_factory=list)


def _check_database() -> tuple[ComponentHealth, ComponentHealth]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            postgis_version = conn.execute(
                text("SELECT postgis_version()")
            ).scalar()
    except Exception as exc:
        message = f"{type(exc).__name__}"
        return (
            ComponentHealth(state="unhealthy", detail=message),
            ComponentHealth(state="unhealthy", detail="database unreachable"),
        )
    return (
        ComponentHealth(state="healthy"),
        ComponentHealth(state="healthy", detail=str(postgis_version)),
    )


def _check_migrations() -> ComponentHealth:
    expected = {"002", "003"}
    try:
        with engine.connect() as conn:
            applied = {
                row[0]
                for row in conn.execute(text("SELECT version FROM schema_migrations"))
            }
    except Exception:
        return ComponentHealth(state="unhealthy", detail="cannot read schema_migrations")

    missing = sorted(expected - applied)
    if missing:
        return ComponentHealth(
            state="unhealthy", detail=f"migrations not applied: {missing}"
        )
    return ComponentHealth(state="healthy", detail=f"applied: {sorted(applied)}")


def _check_classifier() -> ComponentHealth:
    try:
        from app.ml.satellite_classifier import audit_only

        audit = audit_only(settings)
    except Exception as exc:
        return ComponentHealth(state="unhealthy", detail=f"{type(exc).__name__}: {exc}")

    if not audit.exists:
        return ComponentHealth(state="unhealthy", detail="checkpoint missing")
    if not audit.promotion_status.may_persist_observations:
        return ComponentHealth(
            state="not_promoted",
            detail=(
                f"{audit.model_version} is {audit.promotion_status.value}; "
                f"classification output may not be persisted as an observation"
            ),
        )
    return ComponentHealth(
        state="healthy", detail=f"{audit.model_version} {audit.promotion_status.value}"
    )


def _check_satellite_ingestion() -> ComponentHealth:
    if not settings.satellite_enabled:
        return ComponentHealth(
            state="disabled", detail="SATELLITE_ENABLED is false"
        )
    if not settings.has_any_acquisition_credentials:
        return ComponentHealth(
            state="unconfigured",
            detail=(
                "No CDSE acquisition credentials. Discovery is possible; "
                "imagery acquisition is not."
            ),
        )
    return ComponentHealth(
        state="healthy",
        detail=(
            "s3" if settings.has_cdse_s3_credentials else "https/odata"
        ),
    )


def _last_ingestion() -> tuple[str | None, dict[str, Any] | None, dict[str, int]]:
    counts: dict[str, int] = {}
    last_ingest: str | None = None
    last_run: dict[str, Any] | None = None

    try:
        with engine.connect() as conn:
            for table in (
                "satellite_products",
                "satellite_assets",
                "satellite_layers",
                "satellite_changes",
                "satellite_validations",
                "satellite_processing_runs",
                "listings",
            ):
                counts[table] = int(
                    conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
                )

            row = conn.execute(
                text(
                    "SELECT created_at FROM satellite_ingest_log "
                    "WHERE ingestion_status IN ('classified','validated') "
                    "ORDER BY created_at DESC LIMIT 1"
                )
            ).first()
            if row and row[0]:
                last_ingest = row[0].isoformat()

            run = conn.execute(
                text(
                    "SELECT run_id, status, gate_reached, started_at, "
                    "       finished_at, failure_class "
                    "FROM satellite_processing_runs "
                    "ORDER BY started_at DESC LIMIT 1"
                )
            ).mappings().first()
            if run:
                last_run = {
                    "run_id": str(run["run_id"]),
                    "status": run["status"],
                    "gate_reached": run["gate_reached"],
                    "started_at": (
                        run["started_at"].isoformat() if run["started_at"] else None
                    ),
                    "finished_at": (
                        run["finished_at"].isoformat() if run["finished_at"] else None
                    ),
                    "failure_class": run["failure_class"],
                }
    except Exception as exc:
        logger.warning("Readiness counts unavailable: %s", exc)

    return last_ingest, last_run, counts


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Cheap process check. Does not assert anything about dependencies."""
    return HealthResponse(
        status="ok",
        runtime_mode=settings.runtime_mode.value,
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/liveness", response_model=HealthResponse)
def liveness() -> HealthResponse:
    return HealthResponse(
        status="ok",
        runtime_mode=settings.runtime_mode.value,
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/readiness", response_model=ReadinessResponse)
def readiness(response: Response) -> ReadinessResponse:
    """Report real readiness. Returns 503 when not ready to serve.

    In production, an unpromoted model or missing acquisition credentials make
    the service *not ready*: it cannot do the job it claims to do. In
    development and commissioning those are reported but tolerated.
    """
    database, postgis = _check_database()
    migrations = _check_migrations()
    classifier = _check_classifier()
    ingestion = _check_satellite_ingestion()

    problems = settings.validate()
    configuration = (
        ComponentHealth(state="healthy")
        if not problems
        else ComponentHealth(
            state="unhealthy", detail=f"{len(problems)} configuration problem(s)"
        )
    )

    scheduler = ComponentHealth(
        state="healthy" if settings.satellite_scheduler_enabled else "disabled",
        detail=(
            "recurring ingestion enabled"
            if settings.satellite_scheduler_enabled
            else "recurring ingestion disabled pending commissioning"
        ),
    )

    planet = (
        ComponentHealth(state="healthy", detail="PLANET_API_KEY set")
        if settings.has_planet_credentials
        else ComponentHealth(
            state="unconfigured",
            detail=(
                "PLANET_API_KEY not set; validations route to manual review. "
                "No imagery is fabricated."
            ),
        )
    )

    last_ingest, last_run, counts = _last_ingestion()

    # Readiness criteria.
    blocking: list[str] = []
    if database.state != "healthy":
        blocking.append("database unhealthy")
    if postgis.state != "healthy":
        blocking.append("postgis unavailable")
    if migrations.state != "healthy":
        blocking.append(migrations.detail or "migrations not applied")
    if configuration.state != "healthy":
        blocking.extend(problems)

    if settings.runtime_mode is RuntimeMode.PRODUCTION:
        if classifier.state != "healthy":
            blocking.append(classifier.detail or "classifier not promoted")
        if ingestion.state not in ("healthy", "disabled"):
            blocking.append(ingestion.detail or "satellite ingestion unconfigured")

    ready = not blocking
    response.status_code = 200 if ready else 503

    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        runtime_mode=settings.runtime_mode.value,
        timestamp=datetime.utcnow().isoformat(),
        database=database,
        postgis=postgis,
        migrations=migrations,
        classifier=classifier,
        satellite_ingestion=ingestion,
        satellite_scheduler=scheduler,
        planet_validation=planet,
        configuration=configuration,
        last_successful_ingestion=last_ingest,
        last_pipeline_run=last_run,
        counts=counts,
        problems=blocking,
    )
