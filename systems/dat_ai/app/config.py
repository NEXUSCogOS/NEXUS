"""
DAT.AI runtime configuration.

Design rules (non-negotiable):

* Configuration is *explicit*. Nothing that affects scientific validity may be
  inferred from a silent default.
* ``production`` mode fails closed. If a capability required to produce real,
  observed satellite intelligence is unavailable, the process must refuse to
  run rather than substitute simulated data.
* Secrets are never rendered. ``describe()`` reports presence, never value.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class RuntimeMode(str, Enum):
    """Declared operating posture of the process.

    development
        Local engineering. Simulated helpers are permitted but must still be
        explicitly requested; nothing simulated is ever written as ``observed``.
    test
        Automated test suite. No network, no credentials, no database writes to
        the operational database.
    commissioning
        Real credentials, real data, real network — but writes are gated,
        single-product, and reviewed. This is the posture used to walk the
        Gate A..N sequence.
    production
        Real data only. Every synthetic/simulated/placeholder path is hard
        disabled and raises.
    """

    DEVELOPMENT = "development"
    TEST = "test"
    COMMISSIONING = "commissioning"
    PRODUCTION = "production"

    @property
    def forbids_synthetic(self) -> bool:
        """True when simulated/placeholder/random data may not be produced."""
        return self in (RuntimeMode.COMMISSIONING, RuntimeMode.PRODUCTION)

    @property
    def requires_real_credentials(self) -> bool:
        return self in (RuntimeMode.COMMISSIONING, RuntimeMode.PRODUCTION)


class ConfigurationError(RuntimeError):
    """Raised when configuration is invalid for the declared runtime mode."""


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number, got {raw!r}") from exc


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer, got {raw!r}") from exc


# Repository layout anchors. ``config.py`` lives at backend/app/config.py, so
# the DAT.AI root is three parents up.
BACKEND_DIR = Path(__file__).resolve().parent.parent
DAT_AI_ROOT = BACKEND_DIR.parent


@dataclass(frozen=True)
class Settings:
    """Immutable, validated runtime configuration."""

    # ---- runtime posture -------------------------------------------------
    runtime_mode: RuntimeMode

    # ---- database --------------------------------------------------------
    database_url: str

    # ---- satellite master switch ----------------------------------------
    satellite_enabled: bool

    # ---- Copernicus Data Space: catalogue (STAC) ------------------------
    cdse_stac_url: str
    cdse_collection: str

    # ---- Copernicus Data Space: object storage (S3) ---------------------
    cdse_s3_endpoint: str
    cdse_s3_bucket: str
    cdse_s3_access_key: str = field(repr=False, default="")
    cdse_s3_secret_key: str = field(repr=False, default="")
    cdse_s3_region: str = "default"

    # ---- Copernicus Data Space: OData/HTTPS fallback --------------------
    # The STAC assets expose an ``alternate.https`` OData href which requires an
    # OAuth2 token from the CDSE Keycloak identity provider rather than S3 keys.
    cdse_oidc_token_url: str = (
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
        "protocol/openid-connect/token"
    )
    cdse_username: str = field(repr=False, default="")
    cdse_password: str = field(repr=False, default="")

    # ---- Planet Labs (optional validation source) -----------------------
    planet_api_key: str = field(repr=False, default="")

    # ---- acquisition tuning ---------------------------------------------
    satellite_cache_dir: Path = DAT_AI_ROOT / "data" / "satellite_cache"
    satellite_max_cloud_cover: float = 30.0
    satellite_aoi_config: Path = DAT_AI_ROOT / "configs" / "aoi" / "dong_nai.geojson"
    satellite_aoi_name: str = "dong_nai"
    http_timeout_seconds: float = 60.0
    http_max_retries: int = 4

    # ---- model -----------------------------------------------------------
    model_path: Path = BACKEND_DIR / "models" / "satellite_classifier_v1.2.pth"
    model_version: str = "v1.2"
    model_card_path: Path = DAT_AI_ROOT / "docs" / "MODEL_CARD.md"
    # A model may only produce persisted production output when it has been
    # explicitly promoted. See docs/MODEL_CARD.md. Defaults to *not promoted*.
    model_promoted_for_production: bool = False

    # ---- pipeline governance --------------------------------------------
    # Recurring scheduled ingestion stays off until commissioning gates pass.
    satellite_scheduler_enabled: bool = False

    # ---- observability ---------------------------------------------------
    log_level: str = "INFO"
    log_dir: Path = DAT_AI_ROOT / "data" / "logs"
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 5

    # =====================================================================
    # capability predicates
    # =====================================================================

    @property
    def has_cdse_s3_credentials(self) -> bool:
        return bool(self.cdse_s3_access_key and self.cdse_s3_secret_key)

    @property
    def has_cdse_oidc_credentials(self) -> bool:
        return bool(self.cdse_username and self.cdse_password)

    @property
    def has_any_acquisition_credentials(self) -> bool:
        return self.has_cdse_s3_credentials or self.has_cdse_oidc_credentials

    @property
    def has_planet_credentials(self) -> bool:
        return bool(self.planet_api_key)

    @property
    def allow_synthetic_data(self) -> bool:
        """Whether simulated/random/placeholder values may be produced at all."""
        return not self.runtime_mode.forbids_synthetic

    # =====================================================================
    # validation
    # =====================================================================

    def validate(self) -> list[str]:
        """Return a list of configuration problems for the declared mode.

        An empty list means the configuration is valid. Callers (CLI, readiness
        probe, pipeline entry) must treat a non-empty list as fatal in
        commissioning/production.
        """
        problems: list[str] = []

        if not self.database_url:
            problems.append("DATABASE_URL is not set")
        elif not self.database_url.startswith("postgresql"):
            problems.append(
                "DATABASE_URL must be a postgresql:// URL "
                "(DAT.AI requires PostGIS)"
            )

        if self.satellite_max_cloud_cover < 0 or self.satellite_max_cloud_cover > 100:
            problems.append(
                "SATELLITE_MAX_CLOUD_COVER must be between 0 and 100, "
                f"got {self.satellite_max_cloud_cover}"
            )

        if self.http_max_retries < 0:
            problems.append("HTTP_MAX_RETRIES must be >= 0")

        if not self.runtime_mode.requires_real_credentials:
            return problems

        # ---- commissioning / production only ----------------------------
        if not self.cdse_stac_url.startswith("https://"):
            problems.append("CDSE_STAC_URL must be an https:// URL")

        if self.satellite_enabled and not self.has_any_acquisition_credentials:
            problems.append(
                "No Copernicus acquisition credentials configured. Set either "
                "CDSE_S3_ACCESS_KEY + CDSE_S3_SECRET_KEY (S3 access) or "
                "CDSE_USERNAME + CDSE_PASSWORD (OData/HTTPS access). "
                "Discovery alone cannot ingest imagery."
            )

        if self.has_cdse_s3_credentials and not self.cdse_s3_endpoint.startswith(
            "https://"
        ):
            problems.append("CDSE_S3_ENDPOINT must be an https:// URL")

        if not self.satellite_aoi_config.exists():
            problems.append(
                f"SATELLITE_AOI_CONFIG does not exist: {self.satellite_aoi_config}"
            )

        if self.runtime_mode is RuntimeMode.PRODUCTION:
            if not self.model_path.exists():
                problems.append(f"MODEL_PATH does not exist: {self.model_path}")
            if not self.model_promoted_for_production:
                problems.append(
                    "Model is not promoted for production "
                    f"(MODEL_VERSION={self.model_version}). Production "
                    "classification output is refused until MODEL_PROMOTED_FOR_"
                    "PRODUCTION=true and docs/MODEL_CARD.md records real "
                    "held-out evaluation metrics."
                )

        return problems

    def require_valid(self) -> None:
        """Raise ``ConfigurationError`` if configuration is invalid."""
        problems = self.validate()
        if problems:
            rendered = "\n".join(f"  - {p}" for p in problems)
            raise ConfigurationError(
                f"Invalid configuration for runtime_mode="
                f"{self.runtime_mode.value}:\n{rendered}"
            )

    def require_real_data(self, capability: str) -> None:
        """Guard placed at the head of every simulated code path.

        Any function that would produce random, placeholder, demo or otherwise
        unobserved data must call this first. In commissioning/production it
        raises rather than returning fabricated values.
        """
        if self.runtime_mode.forbids_synthetic:
            raise SyntheticDataForbidden(
                f"{capability} attempted to produce simulated data while "
                f"runtime_mode={self.runtime_mode.value}. Production paths must "
                f"fail closed rather than fabricate observations."
            )

    # =====================================================================
    # reporting
    # =====================================================================

    def describe(self) -> dict[str, Any]:
        """Secret-free description suitable for logs, CLI and health output."""

        def presence(value: str) -> str:
            return "set" if value else "NOT SET"

        return {
            "runtime_mode": self.runtime_mode.value,
            "database_url": _redact_dsn(self.database_url),
            "satellite_enabled": self.satellite_enabled,
            "satellite_scheduler_enabled": self.satellite_scheduler_enabled,
            "cdse_stac_url": self.cdse_stac_url,
            "cdse_collection": self.cdse_collection,
            "cdse_s3_endpoint": self.cdse_s3_endpoint,
            "cdse_s3_bucket": self.cdse_s3_bucket,
            "cdse_s3_access_key": presence(self.cdse_s3_access_key),
            "cdse_s3_secret_key": presence(self.cdse_s3_secret_key),
            "cdse_username": presence(self.cdse_username),
            "cdse_password": presence(self.cdse_password),
            "planet_api_key": presence(self.planet_api_key),
            "satellite_cache_dir": str(self.satellite_cache_dir),
            "satellite_aoi_config": str(self.satellite_aoi_config),
            "satellite_aoi_name": self.satellite_aoi_name,
            "satellite_max_cloud_cover": self.satellite_max_cloud_cover,
            "model_path": str(self.model_path),
            "model_version": self.model_version,
            "model_promoted_for_production": self.model_promoted_for_production,
            "log_level": self.log_level,
        }

    def to_json(self) -> str:
        return json.dumps(self.describe(), indent=2, sort_keys=True)


class SyntheticDataForbidden(RuntimeError):
    """Raised when a simulated path is reached under a real-data runtime mode."""


def _redact_dsn(dsn: str) -> str:
    """Strip the password from a postgres DSN for safe display."""
    if "://" not in dsn or "@" not in dsn:
        return dsn
    scheme, rest = dsn.split("://", 1)
    creds, host = rest.rsplit("@", 1)
    user = creds.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"


def load_settings() -> Settings:
    """Build ``Settings`` from the environment.

    Never raises for missing optional values — call ``validate()`` for that, so
    that tooling can report *all* problems at once instead of the first.
    """
    raw_mode = _env("DAT_AI_RUNTIME_MODE", RuntimeMode.DEVELOPMENT.value).lower()
    try:
        mode = RuntimeMode(raw_mode)
    except ValueError as exc:
        valid = ", ".join(m.value for m in RuntimeMode)
        raise ConfigurationError(
            f"DAT_AI_RUNTIME_MODE={raw_mode!r} is not a valid mode. "
            f"Expected one of: {valid}"
        ) from exc

    cache_dir = Path(
        _env("SATELLITE_CACHE_DIR", str(DAT_AI_ROOT / "data" / "satellite_cache"))
    )
    aoi_config = Path(
        _env(
            "SATELLITE_AOI_CONFIG",
            str(DAT_AI_ROOT / "configs" / "aoi" / "dong_nai.geojson"),
        )
    )

    return Settings(
        runtime_mode=mode,
        database_url=_env(
            "DATABASE_URL", "postgresql://datai:datai@db:5432/datai"
        ),
        satellite_enabled=_env_bool("SATELLITE_ENABLED", False),
        cdse_stac_url=_env(
            "CDSE_STAC_URL", "https://stac.dataspace.copernicus.eu/v1/search"
        ),
        cdse_collection=_env("CDSE_COLLECTION", "sentinel-2-l2a"),
        cdse_s3_endpoint=_env(
            "CDSE_S3_ENDPOINT", "https://eodata.dataspace.copernicus.eu"
        ),
        cdse_s3_bucket=_env("CDSE_S3_BUCKET", "eodata"),
        cdse_s3_access_key=_env("CDSE_S3_ACCESS_KEY"),
        cdse_s3_secret_key=_env("CDSE_S3_SECRET_KEY"),
        cdse_s3_region=_env("CDSE_S3_REGION", "default"),
        cdse_username=_env("CDSE_USERNAME"),
        cdse_password=_env("CDSE_PASSWORD"),
        planet_api_key=_env("PLANET_API_KEY"),
        satellite_cache_dir=cache_dir,
        satellite_max_cloud_cover=_env_float("SATELLITE_MAX_CLOUD_COVER", 30.0),
        satellite_aoi_config=aoi_config,
        satellite_aoi_name=_env("SATELLITE_AOI_NAME", "dong_nai"),
        http_timeout_seconds=_env_float("HTTP_TIMEOUT_SECONDS", 60.0),
        http_max_retries=_env_int("HTTP_MAX_RETRIES", 4),
        model_path=Path(
            _env(
                "MODEL_PATH",
                str(BACKEND_DIR / "models" / "satellite_classifier_v1.2.pth"),
            )
        ),
        model_version=_env("MODEL_VERSION", "v1.2"),
        model_promoted_for_production=_env_bool(
            "MODEL_PROMOTED_FOR_PRODUCTION", False
        ),
        satellite_scheduler_enabled=_env_bool("SATELLITE_SCHEDULER_ENABLED", False),
        log_level=_env("LOG_LEVEL", "INFO").upper(),
        log_dir=Path(_env("LOG_DIR", str(DAT_AI_ROOT / "data" / "logs"))),
        log_max_bytes=_env_int("LOG_MAX_BYTES", 10 * 1024 * 1024),
        log_backup_count=_env_int("LOG_BACKUP_COUNT", 5),
    )


settings = load_settings()
