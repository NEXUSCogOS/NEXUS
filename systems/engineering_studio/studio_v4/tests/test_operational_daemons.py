"""Regression fixtures are synthetic tests, never production evidence."""
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from systems.engineering_studio.v6_intelligent_daemon import IntelligentV6Daemon
from systems.engineering_studio.v6_sentinel_daemon import SentinelAutonomousDaemon
from systems.engineering_studio.v6_datai_daemon import DatAIDaemon
from systems.engineering_studio import v6_datai_daemon as datai
from systems.engineering_studio.studio_v3.observatory.evidence_ledger import EvidenceLedger
from systems.engineering_studio.studio_v4.audit_loop.scheduler import AuditScheduler


def test_failed_commands_are_unknown_and_do_not_resolve_issues(tmp_path, monkeypatch):
    daemon = IntelligentV6Daemon(tmp_path)
    daemon._learn({'opportunities': ['launchd_failures', 'cron_broken_paths']})
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(a, 1, '', 'denied'))
    result = daemon.autonomy_loop_with_intelligence()
    assert set(result['observation']['errors']) == {'launchd', 'cron'}
    assert result['analysis']['priority'] != 'nominal'
    assert result['issue_deltas']['newly_resolved'] == []
    with sqlite3.connect(daemon.db_path) as conn:
        assert conn.execute('SELECT launchd_failing_count,cron_missing_count FROM infra_observations').fetchone() == (None, None)


def test_sentinel_normalizes_time_and_excludes_future_and_null_metrics(tmp_path):
    daemon = SentinelAutonomousDaemon(tmp_path / 'runtime')
    daemon.scalper_db_path = tmp_path / 'scalper.db'
    daemon.labs_db_path = tmp_path / 'labs.db'
    with sqlite3.connect(daemon.scalper_db_path) as conn:
        conn.execute('CREATE TABLE pattern_summary(pattern_name,total_occurrences,win_rate,sharpe)')
        conn.executemany('INSERT INTO pattern_summary VALUES(?,?,?,?)', [('valid',25,.6,.4),('null',25,None,None)])
    now = datetime.now(timezone.utc)
    with sqlite3.connect(daemon.labs_db_path) as conn:
        conn.execute('CREATE TABLE lab_signals(ts TEXT, asset TEXT)')
        conn.executemany('INSERT INTO lab_signals VALUES(?,?)', [
            ((now-timedelta(minutes=10)).isoformat(), 'A'),
            ((now-timedelta(minutes=20)).strftime('%Y-%m-%d %H:%M:%S'), 'B'),
            ((now-timedelta(hours=2)).isoformat(), 'OLD'),
            ((now+timedelta(hours=1)).isoformat(), 'FUTURE'),
        ])
    result = daemon.autonomy_loop_financial()
    assert result['observation']['fresh_signal_count_1h'] == 2
    assert result['observation']['unique_assets_1h'] == 2
    assert result['observation']['invalid_pattern_metrics'] == 1
    assert 'signal_clock' in result['observation']['errors']
    assert result['strategies_applied'] is False
    assert result['financial_delta'] is None
    assert result['avg_win_rate_delta'] is None
    assert daemon.autonomy_loop_financial()['avg_win_rate_delta'] == 0
    ledger = EvidenceLedger(tmp_path / 'runtime' / 'operational_evidence.sqlite3')
    try:
        assert ledger.verify_chain() == (True, None)
        assert len(ledger.query_events(agent='sentinel')) == 2
    finally:
        ledger.close()


def test_missing_sources_not_created_or_reported_as_zero(tmp_path):
    daemon = SentinelAutonomousDaemon(tmp_path / 'runtime')
    daemon.scalper_db_path = tmp_path / 'absent_scalper.db'
    daemon.labs_db_path = tmp_path / 'absent_labs.db'
    result = daemon.autonomy_loop_financial()
    assert set(result['observation']['errors']) == {'patterns', 'signals'}
    assert result['observation']['fresh_signal_count_1h'] is None
    assert not daemon.scalper_db_path.exists()
    assert not daemon.labs_db_path.exists()


def test_datai_wal_and_no_execution_claims(tmp_path, monkeypatch):
    db = tmp_path / 'source.db'
    db.write_bytes(b'test')
    Path(str(db)+'-wal').write_bytes(b'wal')
    monkeypatch.setattr(datai, 'DATA_SOURCES', {'source': db})
    daemon = DatAIDaemon(tmp_path / 'runtime')
    result = daemon.autonomy_loop_datai()
    assert result['observation']['source_stats']['source']['file_count'] == 2
    assert result['patterns_applied'] is False
    assert result['efficiency_gain'] is None
    assert result['size_delta_mb'] is None


def test_operational_audit_checks_chain_not_line_count_truth(tmp_path, monkeypatch):
    monkeypatch.setattr(datai, 'DATA_SOURCES', {})
    DatAIDaemon(tmp_path).autonomy_loop_datai()
    scheduler = AuditScheduler(tmp_path/'operational_evidence.sqlite3', tmp_path/'reports')
    try:
        result = scheduler.run_audit_cycle()
        assert result['current_verdict'] == 'OBSERVATIONS_RECORDED'
        assert result['chain_integrity'] == 'PASS'
        assert result['event_count'] == 1
        assert scheduler.run_audit_cycle()['event_count'] == 1
    finally:
        scheduler.close()


def test_healthcheck_process_exit_does_not_encode_observed_health():
    """Health probe execution success must be distinct from observed health."""
    script = (
        Path(__file__).resolve().parents[4]
        / "ops"
        / "monitoring"
        / "production_health_check.sh"
    )

    text = script.read_text()

    assert 'observed_health=HEALTHY' in text
    assert 'observed_health=UNHEALTHY' in text

    # The monitor may observe an unhealthy system without making launchd
    # classify the monitor itself as a failed service.
    assert text.rstrip().endswith("exit 0")
