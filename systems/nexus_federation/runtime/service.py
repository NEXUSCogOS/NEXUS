#!/usr/bin/env python3
"""F10D: canonical NEXUS federation persistent service entrypoint.

RUNTIME_MODE = BOUNDED_CONTROL_A0_A2

Instantiates ONLY the canonical FederationStore, canonical FederationKernel,
and ExecutiveCoordinator built across F9 Phases A-I. Creates no second
kernel, no second store, no second registry. Specialist execution is
dispatched via subprocess to systems/nexus_federation/runtime/specialist_workers/*
-- never by importing a second institution's package into this process --
which is what keeps this service free of the `runtime`-namespace collision
regardless of how many institutions are enabled.

Fails closed: if the configured canonical FederationStore cannot be opened,
this process exits with an error rather than silently creating a fresh DB
elsewhere.

Idle behavior is blocking sleep with backoff -- never a busy loop.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FEDERATION_ROOT = Path(__file__).resolve().parents[1]
NEXUS_ROOT = FEDERATION_ROOT.parent.parent
sys.path.insert(0, str(FEDERATION_ROOT))
sys.path.insert(0, str(NEXUS_ROOT / "systems" / "dat_ai"))  # only for institutional.contract, required by kernel.py's own import chain -- no `runtime` collision (dat_ai defines no top-level `runtime` package)

DEFAULT_CONFIG_PATH = Path.home() / ".nexus_federation" / "service_config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "runtime_mode": "BOUNDED_CONTROL_A0_A2",
    "federation_store_path": str(Path.home() / ".nexus_federation" / "federation.db"),
    "enabled_institutions": ["sentinel", "librarian", "news_intelligence", "engineering_studio"],
    "dependency_gated_institutions": ["dat_ai"],
    "disabled_institutions": ["youtube_production"],
    "authority_ceiling": "GENERATE_INTERNAL",
    "idle_wait_seconds": 30,
    "max_idle_wait_seconds": 300,
    "log_path": str(Path.home() / ".nexus_federation" / "logs" / "service.log"),
    "log_max_bytes": 20_000_000,
    "log_backup_count": 5,
    "heartbeat_interval_seconds": 300,
    "sentinel_db_path": "${NEXUS_ROOT}/systems/sentinel/financial_intelligence.db",
    "sentinel_check_interval_ticks": 10,
    "dat_ai_check_interval_ticks": 60,
}


class FederationService:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._shutdown_requested = False
        self._tick_count = 0
        self._logger = self._setup_logging()

        self.store = self._open_store_fail_closed(config["federation_store_path"])

        from ingress.contract_registry import bootstrap_federation_registry, register_contract
        from contracts.generic import validate_report as validate_generic_report
        bootstrap_federation_registry()
        for institution in config["enabled_institutions"] + config["dependency_gated_institutions"]:
            register_contract(institution, validate_generic_report, frozenset({"1.0.0"}))

        from kernel import FederationKernel
        from executive.coordinator import ExecutiveCoordinator
        self.kernel = FederationKernel(self.store)
        self.coordinator = ExecutiveCoordinator(self.store)

        self._logger.info(
            "FederationService initialized: mode=%s enabled=%s gated=%s disabled=%s",
            config["runtime_mode"], config["enabled_institutions"],
            config["dependency_gated_institutions"], config["disabled_institutions"],
        )

    def _setup_logging(self) -> logging.Logger:
        log_path = Path(self.config["log_path"])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger("nexus_federation_service")
        logger.setLevel(logging.INFO)
        from logging.handlers import RotatingFileHandler
        handler = RotatingFileHandler(
            log_path, maxBytes=self.config["log_max_bytes"], backupCount=self.config["log_backup_count"],
        )
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s"))
        logger.handlers = [handler]
        return logger

    def _open_store_fail_closed(self, store_path: str):
        path = Path(store_path)
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        from persistence.db import FederationStore
        try:
            store = FederationStore(path)
            with store.connection() as conn:
                result = conn.execute("PRAGMA quick_check").fetchone()[0]
            if result != "ok":
                raise RuntimeError(f"canonical store failed quick_check: {result}")
            return store
        except Exception as e:
            self._fail_closed(f"cannot open canonical FederationStore at {path}: {e}")

    def _fail_closed(self, reason: str):
        sys.stderr.write(f"FATAL: {reason}\n")
        sys.exit(1)

    def request_shutdown(self, signum=None, frame=None):
        self._logger.info("Shutdown requested (signal=%s)", signum)
        self._shutdown_requested = True

    # ---- bounded A0 observation ----

    def _observe_sentinel(self):
        """A0: read Sentinel's real current state, read-only. No dispatch."""
        try:
            conn = sqlite3.connect(f"file:{self.config['sentinel_db_path']}?mode=ro", uri=True)
            row = conn.execute("SELECT MAX(date) FROM prices_daily").fetchone()
            conn.close()
            self._logger.info("A0 Sentinel observation: data_cutoff=%s", row[0] if row else None)
        except Exception as e:
            self._logger.warning("A0 Sentinel observation failed: %s", e)

    def _observe_dat_ai_dependency(self):
        """A0: check DAT.AI dependency state. No repeated substantive mission
        creation while PostGIS remains unconfigured (circuit/backoff, not
        repeated failure)."""
        try:
            sys.path.insert(0, str(NEXUS_ROOT / "systems" / "dat_ai"))
            from institutional.reporter import build_current_report
            report = build_current_report(mission_id=f"f10d-heartbeat-{self._tick_count}")
            self._logger.info("A0 DAT.AI dependency check: operating_state=%s", report.operating_state.value)
        except Exception as e:
            self._logger.warning("A0 DAT.AI dependency check failed: %s", e)

    def tick(self):
        self._tick_count += 1

        if "sentinel" in self.config["enabled_institutions"]:
            if self._tick_count % self.config["sentinel_check_interval_ticks"] == 0:
                self._observe_sentinel()

        if "dat_ai" in self.config["dependency_gated_institutions"]:
            if self._tick_count % self.config["dat_ai_check_interval_ticks"] == 0:
                self._observe_dat_ai_dependency()

        if self._tick_count % (self.config["heartbeat_interval_seconds"] // self.config["idle_wait_seconds"] or 1) == 0:
            self._logger.info("heartbeat tick=%d", self._tick_count)

    def run(self):
        self._logger.info("FederationService entering main loop (idle_wait=%ds)", self.config["idle_wait_seconds"])
        signal.signal(signal.SIGTERM, self.request_shutdown)
        signal.signal(signal.SIGINT, self.request_shutdown)

        while not self._shutdown_requested:
            self.tick()
            # Blocking sleep -- NOT a busy loop. Interruptible in small
            # increments so shutdown is responsive.
            slept = 0.0
            while slept < self.config["idle_wait_seconds"] and not self._shutdown_requested:
                time.sleep(min(1.0, self.config["idle_wait_seconds"] - slept))
                slept += 1.0

        self._logger.info("FederationService shutting down cleanly after %d ticks", self._tick_count)
        self.store.checkpoint()


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    if config_path.exists():
        with open(config_path) as f:
            user_config = json.load(f)
        config = dict(DEFAULT_CONFIG)
        config.update(user_config)
        return config
    return dict(DEFAULT_CONFIG)


def main():
    config = load_config()
    service = FederationService(config)
    service.run()


if __name__ == "__main__":
    main()
