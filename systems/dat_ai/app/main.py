"""DAT.AI canonical backend entrypoint.

Recovered into canonical NEXUS during DAT.AI Phase C (2026-08-27). Adapted
from the donor's backend/app/main.py (NEXUS_LOCAL, commit 05c058fb-era) to
wire in only the routes actually recovered this phase: health and zoning.

The donor's main.py also wired properties/satellite/tiles routes and a
background scheduler (app.scheduler). Those routes and their underlying
satellite-acquisition pipeline are NOT part of DAT.AI Phase C's recovery
scope (see DATAI_COMPONENT_RECOVERY_MATRIX.md — they are MODERNIZE-classified
and depend on CDSE/Planet credentials confirmed NOT_FOUND anywhere in this
estate). Including their imports here without porting the modules they need
would either fail to import or silently paper over that gap. This file wires
exactly what canonical DAT.AI can actually serve today.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import RuntimeMode, settings
from app.logging_config import configure_logging, get_logger
from app.routes import health, zoning

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting DAT.AI backend (canonical, Phase C recovery scope)",
        extra={"runtime_mode": settings.runtime_mode.value},
    )

    problems = settings.validate()
    if problems:
        rendered = "\n".join(f"  - {p}" for p in problems)
        if settings.runtime_mode is RuntimeMode.PRODUCTION:
            # Fail closed. A production process must not start while it is
            # misconfigured, because /readiness would then be the only thing
            # standing between a broken deployment and live traffic.
            raise RuntimeError(
                f"Refusing to start in production mode:\n{rendered}"
            )
        logger.warning(
            "Configuration problems (non-fatal in %s mode):\n%s",
            settings.runtime_mode.value,
            rendered,
        )

    yield
    logger.info("Shutting down DAT.AI backend")


app = FastAPI(
    title="DAT.AI Backend (canonical)",
    description=(
        "NEXUS Land / Geospatial Intelligence Institution — zoning model and "
        "API recovered from donor verification (Phase A+B) in Phase C. "
        "Satellite acquisition/inference routes are not yet wired into "
        "canonical NEXUS; see DATAI_PHASE_D_ENTRY_CRITERIA.md."
    ),
    version="0.1.0-phase-c",
    lifespan=lifespan,
)

_allowed_origins = (
    ["*"]
    if settings.runtime_mode
    in (RuntimeMode.DEVELOPMENT, RuntimeMode.TEST, RuntimeMode.COMMISSIONING)
    else [
        origin.strip()
        for origin in (
            __import__("os").getenv("CORS_ALLOW_ORIGINS", "").split(",")
        )
        if origin.strip()
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Structured error response. Never leaks a stack trace to a client."""
    logger.exception(
        "Unhandled error on %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "detail": "An internal error occurred. See server logs.",
            "path": request.url.path,
        },
    )


app.include_router(health.router)
app.include_router(zoning.router)
