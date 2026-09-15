"""Structured, rotating logging.

Rotation is mandatory, not optional: an unbounded satellite pipeline log is a
disk-exhaustion incident waiting to happen. Retention defaults to 5 x 10 MiB
per handler (~50 MiB ceiling).

Secrets are never logged. ``SecretRedactingFilter`` is a defence in depth for
the case where a credential reaches a log record by accident.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import re
import sys
from typing import Any

from app.config import settings

_CONFIGURED = False

# Values that must never appear in a log line, whatever the call site does.
_SECRET_PATTERNS = [
    re.compile(r"(api[-_]?key\s*[=:]\s*)([^\s&\"']+)", re.IGNORECASE),
    re.compile(r"(secret[-_]?key\s*[=:]\s*)([^\s&\"']+)", re.IGNORECASE),
    re.compile(r"(password\s*[=:]\s*)([^\s&\"']+)", re.IGNORECASE),
    re.compile(r"(Bearer\s+)([A-Za-z0-9._\-]{16,})", re.IGNORECASE),
    re.compile(r"(://[^:/@\s]+:)([^@/\s]+)(@)"),  # DSN passwords
]


class SecretRedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True

        redacted = message
        for pattern in _SECRET_PATTERNS:
            redacted = pattern.sub(
                lambda m: m.group(1) + "***" + (m.group(3) if m.lastindex and m.lastindex >= 3 else ""),
                redacted,
            )

        # Also redact any live credential values verbatim.
        for secret in (
            settings.cdse_s3_secret_key,
            settings.cdse_s3_access_key,
            settings.cdse_password,
            settings.planet_api_key,
        ):
            if secret and len(secret) >= 8 and secret in redacted:
                redacted = redacted.replace(secret, "***")

        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


class StructuredFormatter(logging.Formatter):
    """JSON lines with pipeline context fields when present."""

    CONTEXT_FIELDS = (
        "run_id",
        "product_id",
        "stac_id",
        "tile",
        "gate",
        "phase",
        "status",
        "failure_class",
        "duration_seconds",
        "bytes",
        "runtime_mode",
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in self.CONTEXT_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(structured: bool | None = None) -> None:
    """Install console + rotating file handlers exactly once."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    if structured is None:
        structured = os.getenv("LOG_FORMAT", "text").lower() == "json"

    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level, logging.INFO))

    for handler in list(root.handlers):
        root.removeHandler(handler)

    redactor = SecretRedactingFilter()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(
        StructuredFormatter()
        if structured
        else logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
        )
    )
    console.addFilter(redactor)
    root.addHandler(console)

    try:
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            settings.log_dir / "dat_ai.log",
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(StructuredFormatter())
        file_handler.addFilter(redactor)
        root.addHandler(file_handler)
    except OSError as exc:
        root.warning("File logging unavailable (%s); console only", exc)

    # Third-party loggers are noisy at INFO and can echo request URLs.
    for noisy in ("botocore", "boto3", "urllib3", "s3transfer", "rasterio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
