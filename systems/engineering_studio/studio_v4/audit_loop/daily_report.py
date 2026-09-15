"""Daily report generation and Tier 3 archival for the audit loop.

Each audit cycle produces a JSON report file summarizing: event count for
the window, verdict, any alert fired, and a plain-language recommendation.
Reports older than ARCHIVE_AFTER_DAYS are moved into an `archive/` (Tier 3
cold storage) subdirectory rather than deleted, preserving the audit trail.
"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ARCHIVE_AFTER_DAYS = 30
REPORT_FILENAME_FMT = "audit_report_%Y%m%dT%H%M%SZ"


def _recommendation_for(verdict: str, alert: dict | None) -> str:
    if verdict in ('LIKELY_FABRICATED', 'REVIEW_REQUIRED'):
        return 'URGENT review: recorded anomalies require investigation; this is not proof of fabrication.'
    if verdict in ('LIKELY_REAL', 'MIXED', 'INCONCLUSIVE'):
        return 'Insufficient independent evidence to verify work. Line-count variation does not establish truth.'
    if verdict == 'OBSERVATIONS_RECORDED':
        return 'Observations recorded with an intact hash chain. This does not verify upstream data or execution claims.'
    if verdict == 'NO_DATA':
        return 'No producer events in this window. Check producer and ledger configuration.'
    return 'Unrecognized verdict; review manually.'



class DailyReportGenerator:
    """Generates daily audit reports and archives old ones to Tier 3."""

    def __init__(self, reports_dir: str | Path):
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir = self.reports_dir / "archive"

    def generate_report(
        self,
        audit_result: dict,
        alert: dict | None = None,
        now: datetime | None = None,
    ) -> Path:
        """Write a daily report JSON file and return its path."""
        now = now or datetime.now(timezone.utc)
        verdict = audit_result.get("verdict", "UNKNOWN")

        report = {
            "generated_at": now.isoformat(),
            "window_start": audit_result.get("window_start"),
            "window_end": audit_result.get("window_end"),
            "event_count": audit_result.get("event_count", 0),
            "verdict": verdict,
            "chain_integrity": audit_result.get("chain_integrity", "NOT_CHECKED"),
            "scope": audit_result.get("scope"),
            "heuristic_verdict": audit_result.get("heuristic_verdict"),
            "evidence": audit_result.get("evidence", {}),
            "observations_recorded": audit_result.get("observations_recorded", 0),
            "observations_needing_review": audit_result.get("observations_needing_review", []),
            "entries_analyzed": audit_result.get("entries_analyzed", 0),
            "unique_directives": audit_result.get("unique_directives", 0),
            "directives_with_constant_code_lines": audit_result.get(
                "directives_with_constant_code_lines", 0
            ),
            "directives_with_variable_code_lines": audit_result.get(
                "directives_with_variable_code_lines", 0
            ),
            "alert_fired": alert is not None,
            "alert": alert,
            "recommendation": _recommendation_for(verdict, alert),
        }

        stamp = now.strftime(REPORT_FILENAME_FMT)
        report_path = self.reports_dir / f"{stamp}_{uuid.uuid4().hex[:8]}.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        return report_path

    def archive_old_reports(self, now: datetime | None = None, max_age_days: int = ARCHIVE_AFTER_DAYS) -> list[Path]:
        """Move reports older than max_age_days into archive/ (Tier 3).

        Returns the list of new archive paths.
        """
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=max_age_days)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        moved: list[Path] = []
        for path in self.reports_dir.glob("audit_report_*.json"):
            # Filename: audit_report_<YYYYmmddTHHMMSSZ>_<8-hex-uuid>.json
            parts = path.stem.split("_")
            if len(parts) < 4:
                continue
            timestamp_token = parts[2]
            try:
                stamp = datetime.strptime(timestamp_token, "%Y%m%dT%H%M%SZ").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                continue
            if stamp < cutoff:
                dest = self.archive_dir / path.name
                shutil.move(str(path), str(dest))
                moved.append(dest)

        return moved

    def list_reports(self, include_archived: bool = False) -> list[Path]:
        reports = sorted(self.reports_dir.glob("audit_report_*.json"))
        if include_archived:
            reports += sorted(self.archive_dir.glob("audit_report_*.json"))
        return reports
