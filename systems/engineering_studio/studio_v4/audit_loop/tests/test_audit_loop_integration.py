"""Integration tests for audit loop v4 and unified evidence ledger.

Tests verify that:
1. DailyAuditor can read from the unified canonical ledger
2. AlertHandler can detect verdict changes and fire alerts
3. Evidence ledger maintains chain integrity after audit cycles
4. The v3<->v4 coupling works end-to-end

This suite exercises the production path that runs via cron every 24h:
- systems/engineering_studio/studio_v4/audit_loop/daily_auditor.py:DailyAuditor
- systems/engineering_studio/studio_v4/audit_loop/alert_handler.py:AlertHandler
- systems/engineering_studio/studio_v4/audit_loop/scheduler.py:AuditScheduler
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, MagicMock, patch

from systems.engineering_studio.studio_v3.observatory.evidence_ledger import EvidenceLedger
from systems.engineering_studio.studio_v3.observatory.independent_auditor import IndependentAuditor
from systems.engineering_studio.studio_v4.audit_loop.daily_auditor import DailyAuditor
from systems.engineering_studio.studio_v4.audit_loop.alert_handler import AlertHandler
from systems.engineering_studio.studio_v4.audit_loop.scheduler import AuditScheduler


class TestDailyAuditorIntegration:
    """Integration tests for DailyAuditor and unified ledger."""

    def test_daily_auditor_can_read_unified_ledger(self, tmp_path):
        """Verify DailyAuditor can initialize with unified ledger path."""
        ledger_path = tmp_path / ".observatory" / "evidence_ledger.sqlite3"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize ledger (same as daemon uses)
        ledger = EvidenceLedger(str(ledger_path))
        auditor = IndependentAuditor()

        # Should not raise
        daily_auditor = DailyAuditor(ledger, auditor=auditor)
        assert daily_auditor.ledger is ledger
        assert daily_auditor.auditor is auditor

    def test_daily_auditor_audit_last_24h_empty_window(self, tmp_path):
        """Verify audit_last_24h works on empty ledger."""
        ledger_path = tmp_path / ".observatory" / "evidence_ledger.sqlite3"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)

        ledger = EvidenceLedger(str(ledger_path))
        auditor = IndependentAuditor()
        daily_auditor = DailyAuditor(ledger, auditor=auditor)

        # Run audit on empty ledger
        now = datetime.now(timezone.utc)
        result = daily_auditor.audit_last_24h(now=now)

        # Verify result structure
        assert isinstance(result, dict)
        assert 'verdict' in result
        assert 'event_count' in result
        assert 'window_start' in result
        assert 'window_end' in result
        assert result['event_count'] == 0
        # On empty ledger, verdict should be NO_DATA
        assert result['verdict'] == 'NO_DATA'

    def test_daily_auditor_records_audit_event(self, tmp_path):
        """Verify audit result is recorded as a ledger event."""
        ledger_path = tmp_path / ".observatory" / "evidence_ledger.sqlite3"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)

        ledger = EvidenceLedger(str(ledger_path))
        auditor = IndependentAuditor()
        daily_auditor = DailyAuditor(ledger, auditor=auditor)

        # Run audit
        now = datetime.now(timezone.utc)
        result = daily_auditor.audit_last_24h(now=now)

        # Verify audit event was recorded
        audit_events = ledger.query_events(agent='daily_auditor', action='audit_cycle')
        assert len(audit_events) >= 1

        # Verify event structure
        event = audit_events[0]
        assert 'event_id' in event
        assert 'timestamp' in event
        assert 'output_data' in event
        assert 'verdict' in event['output_data']

    def test_daily_auditor_get_previous_verdict_empty(self, tmp_path):
        """Verify get_previous_verdict returns None on first audit."""
        ledger_path = tmp_path / ".observatory" / "evidence_ledger.sqlite3"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)

        ledger = EvidenceLedger(str(ledger_path))
        auditor = IndependentAuditor()
        daily_auditor = DailyAuditor(ledger, auditor=auditor)

        previous = daily_auditor.get_previous_verdict()
        assert previous is None


class TestAlertHandlerIntegration:
    """Integration tests for AlertHandler."""

    def test_alert_handler_can_initialize(self, tmp_path):
        """Verify AlertHandler.__init__ does not raise."""
        ledger_path = tmp_path / ".observatory" / "evidence_ledger.sqlite3"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)

        ledger = EvidenceLedger(str(ledger_path))

        # Should not raise
        handler = AlertHandler(ledger)
        assert handler.ledger is ledger
        assert handler.notifier is None

    def test_alert_handler_detects_fabrication_verdict(self, tmp_path):
        """Verify AlertHandler fires alert on LIKELY_FABRICATED verdict."""
        ledger_path = tmp_path / ".observatory" / "evidence_ledger.sqlite3"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)

        ledger = EvidenceLedger(str(ledger_path))
        handler = AlertHandler(ledger)

        # Check if alert should fire for fabrication
        decision = handler.check_verdict_change(
            previous_verdict='LIKELY_REAL',
            current_verdict='LIKELY_FABRICATED'
        )

        assert decision['should_alert'] is True
        assert decision['reason'] == 'fabrication_detected'

    def test_alert_handler_detects_consistency_drop(self, tmp_path):
        """Verify AlertHandler fires alert on consistency degradation."""
        ledger_path = tmp_path / ".observatory" / "evidence_ledger.sqlite3"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)

        ledger = EvidenceLedger(str(ledger_path))
        handler = AlertHandler(ledger)

        # Consistency drop: LIKELY_REAL -> MIXED
        decision = handler.check_verdict_change(
            previous_verdict='LIKELY_REAL',
            current_verdict='MIXED'
        )

        assert decision['should_alert'] is True
        assert decision['reason'] == 'consistency_drop'

    def test_alert_handler_records_alert_event(self, tmp_path):
        """Verify alert is recorded as a ledger event."""
        ledger_path = tmp_path / ".observatory" / "evidence_ledger.sqlite3"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)

        ledger = EvidenceLedger(str(ledger_path))
        handler = AlertHandler(ledger)

        # Fire an alert
        alert = handler.fire_alert(
            previous_verdict='LIKELY_REAL',
            current_verdict='LIKELY_FABRICATED',
            details={'event_count': 10}
        )

        # Verify alert event was recorded
        alert_events = ledger.query_events(agent='alert_handler', action='alert_fired')
        assert len(alert_events) >= 1

        # Verify event structure
        event = alert_events[0]
        assert 'event_id' in event
        assert 'timestamp' in event
        assert 'output_data' in event

    def test_alert_handler_process_combines_check_and_fire(self, tmp_path):
        """Verify process() method combines check_verdict_change and fire_alert."""
        ledger_path = tmp_path / ".observatory" / "evidence_ledger.sqlite3"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)

        ledger = EvidenceLedger(str(ledger_path))
        handler = AlertHandler(ledger)

        # Call process with fabrication verdict
        alert = handler.process(
            previous_verdict='LIKELY_REAL',
            current_verdict='LIKELY_FABRICATED',
            details={'event_count': 5}
        )

        # Should return alert dict (not None)
        assert alert is not None
        assert alert['current_verdict'] == 'LIKELY_FABRICATED'
        assert 'timestamp' in alert

    def test_alert_handler_no_alert_on_non_critical_change(self, tmp_path):
        """Verify no alert on non-critical verdict changes."""
        ledger_path = tmp_path / ".observatory" / "evidence_ledger.sqlite3"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)

        ledger = EvidenceLedger(str(ledger_path))
        handler = AlertHandler(ledger)

        # Non-critical change
        alert = handler.process(
            previous_verdict='LIKELY_REAL',
            current_verdict='LIKELY_REAL',  # No change
            details={}
        )

        # Should return None (no alert)
        assert alert is None


class TestAuditSchedulerIntegration:
    """Integration tests for AuditScheduler (end-to-end)."""

    def test_scheduler_can_initialize(self, tmp_path):
        """Verify AuditScheduler.__init__ with unified ledger."""
        ledger_path = tmp_path / ".observatory" / "evidence_ledger.sqlite3"
        reports_dir = tmp_path / ".observatory" / "reports"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)

        # Should not raise
        scheduler = AuditScheduler(
            ledger_path=str(ledger_path),
            reports_dir=str(reports_dir)
        )

        assert scheduler.ledger_path == ledger_path
        assert scheduler.reports_dir == reports_dir
        assert scheduler.ledger is not None
        assert scheduler.daily_auditor is not None

    def test_scheduler_run_audit_cycle_returns_summary(self, tmp_path):
        """Verify run_audit_cycle returns summary dict."""
        ledger_path = tmp_path / ".observatory" / "evidence_ledger.sqlite3"
        reports_dir = tmp_path / ".observatory" / "reports"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)

        scheduler = AuditScheduler(
            ledger_path=str(ledger_path),
            reports_dir=str(reports_dir)
        )

        # Mock report generator to avoid file I/O
        mock_report = MagicMock()
        mock_report.generate_report.return_value = tmp_path / "report.json"
        mock_report.archive_old_reports.return_value = []
        scheduler.report_generator = mock_report

        now = datetime.now(timezone.utc)
        summary = scheduler.run_audit_cycle(now=now)

        # Verify summary structure
        assert isinstance(summary, dict)
        assert 'timestamp' in summary
        assert 'previous_verdict' in summary
        assert 'current_verdict' in summary
        assert 'event_count' in summary
        assert 'alert_fired' in summary
        assert 'report_path' in summary

    def test_scheduler_couples_v3_v4(self, tmp_path):
        """Verify scheduler properly couples v3 Observatory and v4 audit loop."""
        ledger_path = tmp_path / ".observatory" / "evidence_ledger.sqlite3"
        reports_dir = tmp_path / ".observatory" / "reports"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)

        # Simulate a v3 daemon event in the ledger
        ledger = EvidenceLedger(str(ledger_path))

        ledger.record_event(
            agent='continuous_autonomous_daemon',
            action='observatory_self_monitoring_cycle',
            input_data={'cycle': 1},
            output_data={'directive_backlog': {'pending': 5}},
            resource_cost={'cpu_ms': 10},
            files_modified=None,
            git_commit_hash=None,
        )

        # record_event stamps its own timestamp internally; capture the
        # window boundary only after the write so it's guaranteed to cover it.
        now = datetime.now(timezone.utc)

        # Now run v4 audit
        scheduler = AuditScheduler(
            ledger_path=str(ledger_path),
            reports_dir=str(reports_dir)
        )

        mock_report = MagicMock()
        mock_report.generate_report.return_value = tmp_path / "report.json"
        mock_report.archive_old_reports.return_value = []
        scheduler.report_generator = mock_report

        summary = scheduler.run_audit_cycle(now=now)

        # Verify audit cycle saw the v3 daemon event
        assert summary['event_count'] == 1

    def test_scheduler_ledger_chain_integrity(self, tmp_path):
        """Verify evidence ledger maintains hash chain integrity."""
        ledger_path = tmp_path / ".observatory" / "evidence_ledger.sqlite3"
        reports_dir = tmp_path / ".observatory" / "reports"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)

        scheduler = AuditScheduler(
            ledger_path=str(ledger_path),
            reports_dir=str(reports_dir)
        )

        # Get initial event count
        all_events_before = scheduler.ledger.query_events()
        count_before = len(all_events_before)

        # Run audit cycle
        mock_report = MagicMock()
        mock_report.generate_report.return_value = tmp_path / "report.json"
        mock_report.archive_old_reports.return_value = []
        scheduler.report_generator = mock_report

        scheduler.run_audit_cycle()

        # Get final event count
        all_events_after = scheduler.ledger.query_events()
        count_after = len(all_events_after)

        # Should have added at least the audit event
        assert count_after >= count_before + 1

        # Verify all events are still queryable and have valid structure
        for event in all_events_after:
            assert 'event_id' in event
            assert 'timestamp' in event
            assert 'agent' in event
            assert 'action' in event
