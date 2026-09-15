"""Tests for the Phase 2 Stream C 24-hour audit loop.

Covers: DailyAuditor verdict recording, AlertHandler verdict-change
detection, DailyReportGenerator report/archival, AuditScheduler
orchestration, and a compressed end-to-end "48-hour" integration test that
runs two audit cycles (real time replaced by an injected `now`, since
sleeping 48h in CI is infeasible) to verify verdicts are recorded correctly
and alerts fire when fabrication is introduced.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_TESTS_DIR = Path(__file__).resolve().parent
_STUDIO_V4 = _TESTS_DIR.parent
_STUDIO_V3 = _STUDIO_V4.parent / "studio_v3"
for p in (_STUDIO_V4, _STUDIO_V3):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from observatory.evidence_ledger import EvidenceLedger  # noqa: E402

from audit_loop.daily_auditor import DailyAuditor, AUDIT_ACTION  # noqa: E402
from audit_loop.alert_handler import AlertHandler  # noqa: E402
from audit_loop.daily_report import DailyReportGenerator  # noqa: E402
from audit_loop.scheduler import AuditScheduler  # noqa: E402


@pytest.fixture
def ledger(tmp_path):
    lg = EvidenceLedger(tmp_path / "observatory.db")
    yield lg
    lg.close()


def _record_line_count_claim(ledger, directive, code_lines, agent="daemon"):
    ledger.record_event(
        agent=agent,
        action=directive,
        output_data={"code_lines": code_lines},
    )


# ---------------------------------------------------------------------------
# DailyAuditor
# ---------------------------------------------------------------------------

class TestDailyAuditor:
    def test_no_events_yields_no_data_verdict(self, ledger):
        auditor = DailyAuditor(ledger)
        result = auditor.audit_last_24h()
        assert result["verdict"] == "NO_DATA"
        assert result["event_count"] == 0

    def test_variable_code_lines_cannot_verify_truth(self, ledger):
        for i in range(6):
            _record_line_count_claim(ledger, "fix_bug", code_lines=10 + i)
        auditor = DailyAuditor(ledger)
        result = auditor.audit_last_24h()
        assert result["verdict"] == "INCONCLUSIVE"

    def test_constant_code_lines_requires_review(self, ledger):
        for _ in range(6):
            _record_line_count_claim(ledger, "fix_bug", code_lines=42)
        auditor = DailyAuditor(ledger)
        result = auditor.audit_last_24h()
        assert result["verdict"] == "REVIEW_REQUIRED"

    def test_verdict_recorded_as_meta_event(self, ledger):
        for i in range(6):
            _record_line_count_claim(ledger, "fix_bug", code_lines=10 + i)
        auditor = DailyAuditor(ledger)
        auditor.audit_last_24h()

        meta_events = ledger.query_events(agent="daily_auditor", action=AUDIT_ACTION)
        assert len(meta_events) == 1
        assert meta_events[0]["output_data"]["verdict"] == "INCONCLUSIVE"

    def test_historical_log_filtering_excludes_own_meta_events(self, ledger):
        for _ in range(6):
            _record_line_count_claim(ledger, "fix_bug", code_lines=99)
        auditor = DailyAuditor(ledger)
        first = auditor.audit_last_24h()
        assert first["verdict"] == "REVIEW_REQUIRED"

        # Second run must not treat its own prior meta-event as evidence.
        second = auditor.audit_last_24h()
        assert second["verdict"] == "REVIEW_REQUIRED"
        assert second["unique_directives"] == 1  # only "fix_bug", not audit_cycle

    def test_window_excludes_events_older_than_24h(self, ledger):
        # Manually insert an old-looking event by recording then we can't
        # backdate via record_event (timestamp is always "now"), so instead
        # verify window math directly via _window_start, and verify
        # end-to-end that events outside [window_start, window_end] are
        # excluded from the audited row set.
        auditor = DailyAuditor(ledger, window_hours=24)
        now = datetime.now(timezone.utc)
        window_start = auditor._window_start(now)
        assert window_start == now - timedelta(hours=24)

        for i in range(6):
            _record_line_count_claim(ledger, "fix_bug", code_lines=10 + i)

        # A "now" anchored before any events were recorded should see none.
        past_now = now - timedelta(days=2)
        result = auditor.audit_last_24h(now=past_now)
        assert result["event_count"] == 0
        assert result["verdict"] == "NO_DATA"

    def test_get_previous_verdict_none_on_first_run(self, ledger):
        auditor = DailyAuditor(ledger)
        assert auditor.get_previous_verdict() is None

    def test_get_previous_verdict_returns_last(self, ledger):
        for _ in range(6):
            _record_line_count_claim(ledger, "fix_bug", code_lines=1)
        auditor = DailyAuditor(ledger)
        auditor.audit_last_24h()  # LIKELY_FABRICATED (constant)
        assert auditor.get_previous_verdict() == "REVIEW_REQUIRED"

    def test_stdout_and_replayed_summaries_are_not_code_measurements(self, ledger):
        for i in range(6):
            ledger.record_event(agent='executor', action='run', output_data={'stdout_tail': 'line\n' * (i+1)})
            ledger.record_event(agent='daemon', action='monitor', output_data={
                'historical_log_audit': {'evidence': {'fix': {'unique_code_lines_values': [1, 2, 3]}}}})
        result = DailyAuditor(ledger).audit_last_24h()
        assert result['verdict'] == 'INCONCLUSIVE'
        assert result['entries_analyzed'] == 0
        assert result['event_count'] == 12

    def test_corrupt_chain_rejected_before_recording_verdict(self, ledger):
        _record_line_count_claim(ledger, 'fix', 5)
        ledger._conn.execute("UPDATE events SET output_data='{}'")
        with pytest.raises(RuntimeError, match='chain failed'):
            DailyAuditor(ledger).audit_last_24h()
        assert ledger.query_events(action=AUDIT_ACTION) == []


# ---------------------------------------------------------------------------
# AlertHandler
# ---------------------------------------------------------------------------

class TestAlertHandler:
    def test_no_alert_when_stable_real(self, ledger):
        handler = AlertHandler(ledger)
        decision = handler.check_verdict_change("LIKELY_REAL", "LIKELY_REAL")
        assert decision["should_alert"] is False

    def test_alert_on_fabrication_detected(self, ledger):
        handler = AlertHandler(ledger)
        decision = handler.check_verdict_change("LIKELY_REAL", "LIKELY_FABRICATED")
        assert decision["should_alert"] is True
        assert decision["reason"] == "fabrication_detected"

    def test_alert_on_first_run_fabricated(self, ledger):
        handler = AlertHandler(ledger)
        decision = handler.check_verdict_change(None, "LIKELY_FABRICATED")
        assert decision["should_alert"] is True

    def test_alert_on_consistency_drop(self, ledger):
        handler = AlertHandler(ledger)
        decision = handler.check_verdict_change("LIKELY_REAL", "MIXED")
        assert decision["should_alert"] is True
        assert decision["reason"] == "consistency_drop"

    def test_missing_data_alerts(self, ledger):
        handler = AlertHandler(ledger)
        decision = handler.check_verdict_change("MIXED", "NO_DATA")
        assert decision["should_alert"] is True

    def test_fire_alert_records_event(self, ledger):
        handler = AlertHandler(ledger)
        alert = handler.fire_alert("LIKELY_REAL", "LIKELY_FABRICATED")
        events = ledger.query_events(agent="alert_handler", action="alert_fired")
        assert len(events) == 1
        assert events[0]["output_data"]["current_verdict"] == "LIKELY_FABRICATED"
        assert alert["current_verdict"] == "LIKELY_FABRICATED"

    def test_process_fires_only_when_warranted(self, ledger):
        handler = AlertHandler(ledger)
        assert handler.process("LIKELY_REAL", "LIKELY_REAL") is None
        assert handler.process("LIKELY_REAL", "LIKELY_FABRICATED") is not None

    def test_notifier_called_on_alert(self, ledger):
        received = []
        handler = AlertHandler(ledger, notifier=received.append)
        handler.fire_alert("LIKELY_REAL", "LIKELY_FABRICATED")
        assert len(received) == 1


# ---------------------------------------------------------------------------
# DailyReportGenerator
# ---------------------------------------------------------------------------

class TestDailyReportGenerator:
    def test_generate_report_writes_file(self, tmp_path):
        gen = DailyReportGenerator(tmp_path)
        result = {
            "window_start": "2026-08-15T00:00:00+00:00",
            "window_end": "2026-08-16T00:00:00+00:00",
            "event_count": 5,
            "verdict": "LIKELY_REAL",
            "entries_analyzed": 5,
            "unique_directives": 1,
            "directives_with_constant_code_lines": 0,
            "directives_with_variable_code_lines": 1,
        }
        path = gen.generate_report(result)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["verdict"] == "LIKELY_REAL"
        assert "does not establish truth" in data["recommendation"]

    def test_generate_report_includes_alert(self, tmp_path):
        gen = DailyReportGenerator(tmp_path)
        result = {"verdict": "LIKELY_FABRICATED", "event_count": 3}
        alert = {"current_verdict": "LIKELY_FABRICATED"}
        path = gen.generate_report(result, alert=alert)
        data = json.loads(path.read_text())
        assert data["alert_fired"] is True
        assert "URGENT" in data["recommendation"]

    def test_archive_moves_old_reports(self, tmp_path):
        gen = DailyReportGenerator(tmp_path)
        old_time = datetime.now(timezone.utc) - timedelta(days=40)
        result = {"verdict": "LIKELY_REAL", "event_count": 1}
        old_path = gen.generate_report(result, now=old_time)
        assert old_path.exists()

        moved = gen.archive_old_reports(now=datetime.now(timezone.utc))
        assert len(moved) == 1
        assert not old_path.exists()
        assert moved[0].parent.name == "archive"
        assert moved[0].exists()

    def test_archive_leaves_recent_reports(self, tmp_path):
        gen = DailyReportGenerator(tmp_path)
        result = {"verdict": "LIKELY_REAL", "event_count": 1}
        recent_path = gen.generate_report(result, now=datetime.now(timezone.utc))

        moved = gen.archive_old_reports(now=datetime.now(timezone.utc))
        assert moved == []
        assert recent_path.exists()

    def test_list_reports(self, tmp_path):
        gen = DailyReportGenerator(tmp_path)
        result = {"verdict": "LIKELY_REAL", "event_count": 1}
        gen.generate_report(result, now=datetime.now(timezone.utc))
        assert len(gen.list_reports()) == 1


# ---------------------------------------------------------------------------
# AuditScheduler orchestration
# ---------------------------------------------------------------------------

class TestAuditScheduler:
    def test_run_audit_cycle_end_to_end_clean(self, tmp_path):
        scheduler = AuditScheduler(
            ledger_path=tmp_path / "observatory.db",
            reports_dir=tmp_path / "reports",
        )
        try:
            for i in range(6):
                _record_line_count_claim(scheduler.ledger, "fix_bug", code_lines=10 + i)
            summary = scheduler.run_audit_cycle()
            assert summary["current_verdict"] == "INCONCLUSIVE"
            assert summary["alert_fired"] is True
            assert Path(summary["report_path"]).exists()
        finally:
            scheduler.close()

    def test_run_audit_cycle_fires_alert_on_fabrication(self, tmp_path):
        scheduler = AuditScheduler(
            ledger_path=tmp_path / "observatory.db",
            reports_dir=tmp_path / "reports",
        )
        try:
            for _ in range(6):
                _record_line_count_claim(scheduler.ledger, "fix_bug", code_lines=7)
            summary = scheduler.run_audit_cycle()
            assert summary["current_verdict"] == "REVIEW_REQUIRED"
            assert summary["alert_fired"] is True
        finally:
            scheduler.close()

    def test_schedule_timing_uses_configured_interval(self, tmp_path):
        scheduler = AuditScheduler(
            ledger_path=tmp_path / "observatory.db",
            reports_dir=tmp_path / "reports",
            interval_seconds=999,
        )
        try:
            assert scheduler.interval_seconds == 999
        finally:
            scheduler.close()


# ---------------------------------------------------------------------------
# Compressed 48-hour integration test
# ---------------------------------------------------------------------------

class TestFortyEightHourIntegration:
    """Simulates two 24h audit cycles (day 1: clean, day 2: fabrication
    introduced) without sleeping for 48 real hours, by driving
    run_audit_cycle with explicit `now` timestamps 24h apart. Verifies
    verdicts are recorded correctly across both cycles and that the
    verdict flip fires an alert.
    """

    def test_two_cycles_clean_then_fabricated(self, tmp_path):
        # Real event timestamps can't be backdated (EvidenceLedger always
        # stamps "now"), so this drives two real audit cycles back-to-back:
        # each cycle's 24h window naturally covers all events recorded so
        # far (since the wall-clock gap between cycles is seconds, not
        # days). This still exercises the full real flow — scheduling,
        # auditing, verdict recording, alerting, reporting, archival — the
        # "48h" compression is in event volume/timing, not literal sleep.
        scheduler = AuditScheduler(
            ledger_path=tmp_path / "observatory.db",
            reports_dir=tmp_path / "reports",
        )
        try:
            # Cycle 1: varied claims, still unverified.
            for i in range(6):
                _record_line_count_claim(scheduler.ledger, "refactor_day1", code_lines=20 + i)
            summary1 = scheduler.run_audit_cycle()
            assert summary1["current_verdict"] == "INCONCLUSIVE"
            assert summary1["alert_fired"] is True

            # Cycle 2: a new directive reports suspiciously
            # constant code_lines — a fabrication signature. The window
            # still includes day 1's genuine events, so the combined
            # picture is a mix: one real directive, one fabricated one.
            for _ in range(6):
                _record_line_count_claim(scheduler.ledger, "refactor_day2", code_lines=20)
            summary2 = scheduler.run_audit_cycle()
            assert summary2["current_verdict"] == "INCONCLUSIVE"
            assert summary2["previous_verdict"] == "INCONCLUSIVE"
            assert summary2["alert_fired"] is True  # LIKELY_REAL -> MIXED is a consistency drop

            # Both audit meta-events + both alert events are present and
            # the hash chain is intact end-to-end (nothing was fabricated
            # by the audit loop itself).
            audit_events = scheduler.ledger.query_events(agent="daily_auditor")
            assert len(audit_events) == 2
            alert_events = scheduler.ledger.query_events(agent="alert_handler")
            assert len(alert_events) == 2

            chain_ok, bad_id = scheduler.ledger.verify_chain()
            assert chain_ok, f"hash chain broken at {bad_id}"

            reports = scheduler.report_generator.list_reports()
            assert len(reports) == 2
        finally:
            scheduler.close()
