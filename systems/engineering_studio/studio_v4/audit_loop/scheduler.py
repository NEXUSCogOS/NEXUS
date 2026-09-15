"""Scheduler & orchestration for the 24-hour audit loop.

Uses native stdlib scheduling (threading.Timer-driven loop) rather than
APScheduler: APScheduler is not installed in this environment and the
project's global constraint is stdlib + existing dependencies only, no new
external packages without justification. A cron-based deployment path is
also provided (see `cron/` config and `run_audit_cycle_cli` entry point)
for environments that prefer OS-level scheduling over an in-process loop.

AuditScheduler wires together DailyAuditor, AlertHandler and
DailyReportGenerator into a single `run_audit_cycle()` call, and can either
run that on an in-process 24h interval (`schedule_audit_cycle`) or be
invoked once per cron tick from the command line.
"""

from __future__ import annotations

import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from systems.engineering_studio.studio_v3.observatory.evidence_ledger import EvidenceLedger
from systems.engineering_studio.studio_v3.observatory.independent_auditor import IndependentAuditor

from .daily_auditor import DailyAuditor
from .alert_handler import AlertHandler
from .daily_report import DailyReportGenerator

DEFAULT_INTERVAL_SECONDS = 24 * 60 * 60


class AuditScheduler:
    """Orchestrates one audit cycle and (optionally) runs it every 24h."""

    def __init__(
        self,
        ledger_path: str | Path,
        reports_dir: str | Path,
        interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
        notifier=None,
    ):
        self.ledger_path = Path(ledger_path)
        self.reports_dir = Path(reports_dir)
        self.interval_seconds = interval_seconds

        self.ledger = EvidenceLedger(self.ledger_path)
        self.daily_auditor = DailyAuditor(self.ledger, IndependentAuditor())
        self.alert_handler = AlertHandler(self.ledger, notifier=notifier)
        self.report_generator = DailyReportGenerator(self.reports_dir)

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def run_audit_cycle(self, now: datetime | None = None) -> dict:
        """Execute a single audit cycle: audit -> alert check -> report ->
        archival. Returns a summary dict. This is the unit cron would invoke
        once per day, and is also what the in-process loop calls repeatedly.
        """
        now = now or datetime.now(timezone.utc)

        previous_verdict = self.daily_auditor.get_previous_verdict()
        result = self.daily_auditor.audit_last_24h(now=now)
        current_verdict = result["verdict"]

        alert = self.alert_handler.process(
            previous_verdict,
            current_verdict,
            details={"event_count": result["event_count"]},
        )

        report_path = self.report_generator.generate_report(result, alert=alert, now=now)
        archived = self.report_generator.archive_old_reports(now=now)

        return {
            "timestamp": now.isoformat(),
            "previous_verdict": previous_verdict,
            "current_verdict": current_verdict,
            "chain_integrity": result.get("chain_integrity"),
            "scope": result.get("scope"),
            "event_count": result["event_count"],
            "alert_fired": alert is not None,
            "report_path": str(report_path),
            "archived_reports": [str(p) for p in archived],
        }

    def schedule_audit_cycle(self, run_immediately: bool = False, blocking: bool = False) -> None:
        """Start an in-process loop that runs `run_audit_cycle` every
        `interval_seconds`. Runs in a background thread unless `blocking`
        is True (useful for tests / cron-style single invocation via
        `interval_seconds=0`).
        """
        self._stop_event.clear()

        def _loop():
            if run_immediately:
                self.run_audit_cycle()
            while not self._stop_event.wait(self.interval_seconds):
                self.run_audit_cycle()

        if blocking:
            _loop()
        else:
            self._thread = threading.Thread(target=_loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def close(self) -> None:
        self.stop()
        self.ledger.close()


def run_audit_cycle_cli() -> int:
    """CLI entry point for cron: `python -m audit_loop.scheduler`.

    Reads ledger/report paths from environment variables (with sensible
    defaults under systems/engineering_studio/studio_v4/data/), runs one
    audit cycle, prints the summary, and exits 0. Intended to be invoked by
    an OS-level cron entry once per day.
    """
    import json
    import os

    base = Path(__file__).resolve().parents[2] / "runtime"
    ledger_path = os.environ.get("AUDIT_LOOP_LEDGER_PATH", str(base / "operational_evidence.sqlite3"))
    reports_dir = os.environ.get("AUDIT_LOOP_REPORTS_DIR", str(base / "audit_reports"))

    scheduler = AuditScheduler(ledger_path=ledger_path, reports_dir=reports_dir)
    try:
        summary = scheduler.run_audit_cycle()
    finally:
        scheduler.close()

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run_audit_cycle_cli())
