"""
Engineering Studio V6 - INFRASTRUCTURE HEALTH DAEMON
Real observation of NEXUS automation health: LaunchAgents, crontab, disk space.
Every OBSERVE value is a live measurement. Nothing here is simulated or random.
"""

import json
import shutil
import sqlite3
import subprocess
import shlex
from datetime import datetime, timezone
from pathlib import Path

try:
    from .operational_evidence import record_cycle
except ImportError:
    from operational_evidence import record_cycle

HOME = Path.home()


class IntelligentV6Daemon:
    def __init__(self, runtime_path=None):
        self.runtime_path = Path(runtime_path) if runtime_path else Path(__file__).resolve().parent / "runtime"
        self.runtime_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.runtime_path / "v6_canonical.db"
        self._ensure_schema()

    def _ensure_schema(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS infra_observations (
                id INTEGER PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                disk_free_gb REAL,
                disk_pct_used REAL,
                launchd_failing_count INTEGER,
                launchd_failing_labels TEXT,
                cron_missing_count INTEGER,
                cron_missing_paths TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS infra_issues (
                id INTEGER PRIMARY KEY,
                issue_key TEXT,
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                consecutive_cycles INTEGER DEFAULT 1,
                resolved_at DATETIME
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS daemon_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def autonomy_loop_with_intelligence(self):
        """OBSERVE -> ANALYZE -> LEARN -> OPTIMIZE -> UPDATE, all on real state."""
        observation = self._observe()
        analysis = self._analyze(observation)
        issue_deltas = self._learn(analysis)
        optimization = self._summarize(observation, analysis, issue_deltas)
        self._update_memory(observation, optimization)

        result = {
            'observation': observation,
            'analysis': analysis,
            'issue_deltas': issue_deltas,
            'performance_delta': optimization['net_issues_delta'],
            'decisions_made': optimization['recommendations'],
        }

        result["evidence_event_id"] = record_cycle(self.runtime_path, "infra", result)
        return result

    def _observe(self):
        """OBSERVE: real disk usage, real LaunchAgent exit codes, real crontab path checks."""
        total, used, free = shutil.disk_usage("/")
        disk_free_gb = free / (1024 ** 3)
        disk_pct_used = used / total * 100

        self.observation_errors = {}
        launchd_failing = self._observe_launchd()
        cron_missing = self._observe_crontab()

        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'disk_free_gb': round(disk_free_gb, 2),
            'disk_pct_used': round(disk_pct_used, 1),
            'launchd_failing': launchd_failing,
            'cron_missing': cron_missing,
            'errors': self.observation_errors.copy(),
        }

    def _observe_launchd(self):
        """Real launchctl list parse: any user LaunchAgent with nonzero last exit status."""
        try:
            proc = subprocess.run(
                ["launchctl", "list"], capture_output=True, text=True, timeout=10
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                raise RuntimeError(f"launchctl failed ({proc.returncode}): {proc.stderr.strip()}")
            out = proc.stdout
        except Exception as e:
            self.observation_errors['launchd'] = str(e)
            return []

        failing = []
        for line in out.splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            pid, status, label = parts
            if not (label.startswith("com.scalper") or label.startswith("com.labs")
                    or label.startswith("com.nexus") or label.startswith("com.studio")):
                continue
            try:
                status_int = int(status)
            except ValueError:
                continue
            if status_int != 0:
                failing.append({'label': label, 'last_exit_status': status_int})
        return failing

    def _observe_crontab(self):
        """Real crontab parse: for every command line, check the referenced script path exists."""
        try:
            proc = subprocess.run(
                ["crontab", "-l"], capture_output=True, text=True, timeout=10
            )
            if proc.returncode != 0:
                if proc.returncode == 1 and "no crontab for" in proc.stderr.lower():
                    return []
                raise RuntimeError(f"crontab failed ({proc.returncode}): {proc.stderr.strip()}")
            out = proc.stdout
        except Exception as e:
            self.observation_errors['cron'] = str(e)
            return []

        missing = []
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                tokens = shlex.split(line, comments=True)
            except ValueError as exc:
                self.observation_errors["cron"] = f"cannot parse crontab: {exc}"
                continue
            for token in tokens:
                if token.startswith("/") and token.endswith((".py", ".sh")):
                    if not Path(token).exists():
                        missing.append(token)
        return sorted(set(missing))

    def _analyze(self, observation):
        """ANALYZE: real thresholds against real observed values."""
        opportunities = []

        if observation['disk_free_gb'] < 10:
            opportunities.append('low_disk_space')
        if observation['launchd_failing']:
            opportunities.append('launchd_failures')
        if observation['cron_missing']:
            opportunities.append('cron_broken_paths')

        errors = observation.get('errors', {})
        opportunities.extend('observation_failed:' + key for key in sorted(errors))
        unknown_keys = []
        if 'launchd' in errors:
            unknown_keys.append('launchd_failures')
        if 'cron' in errors:
            unknown_keys.append('cron_broken_paths')
        return {
            'unknown_keys': unknown_keys,
            'opportunities': opportunities,
            'priority': 'urgent' if 'low_disk_space' in opportunities else (
                'attention' if opportunities else 'nominal'
            ),
        }

    def _learn(self, analysis):
        """LEARN: track real issue persistence across cycles (not a fixed dict)."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        now = datetime.now(timezone.utc).isoformat()
        active_keys = set(analysis['opportunities'])

        c.execute("SELECT issue_key FROM infra_issues WHERE resolved_at IS NULL")
        previously_open = {row[0] for row in c.fetchall()}

        newly_opened, still_open, newly_resolved = [], [], []

        for key in active_keys:
            if key in previously_open:
                c.execute(
                    "UPDATE infra_issues SET last_seen=?, consecutive_cycles=consecutive_cycles+1 "
                    "WHERE issue_key=? AND resolved_at IS NULL",
                    (now, key),
                )
                still_open.append(key)
            else:
                c.execute(
                    "INSERT INTO infra_issues (issue_key, first_seen, last_seen, consecutive_cycles) "
                    "VALUES (?, ?, ?, 1)",
                    (key, now, now),
                )
                newly_opened.append(key)

        for key in previously_open - active_keys - set(analysis.get('unknown_keys', [])):
            c.execute(
                "UPDATE infra_issues SET resolved_at=? WHERE issue_key=? AND resolved_at IS NULL",
                (now, key),
            )
            newly_resolved.append(key)

        conn.commit()
        conn.close()

        return {
            'newly_opened': newly_opened,
            'still_open': still_open,
            'newly_resolved': newly_resolved,
        }

    def _summarize(self, observation, analysis, issue_deltas):
        """OPTIMIZE: honest recommendations grounded in what was actually observed."""
        recommendations = []

        if 'low_disk_space' in analysis['opportunities']:
            recommendations.append({
                'issue': 'low_disk_space',
                'detail': f"{observation['disk_free_gb']}GB free ({observation['disk_pct_used']}% used)",
                'action': 'investigate largest growing directories under ~/.local/logs',
            })
        for f in observation['launchd_failing']:
            recommendations.append({
                'issue': 'launchd_failure',
                'detail': f"{f['label']} last exit status {f['last_exit_status']}",
                'action': 'check plist ProgramArguments path exists and stderr log',
            })
        for path in observation['cron_missing']:
            recommendations.append({
                'issue': 'cron_broken_path',
                'detail': path,
                'action': 'update crontab entry or restore the missing file',
            })

        for source, error in observation.get('errors', {}).items():
            recommendations.append({'issue': 'observation_failed', 'detail': source + ': ' + error,
                                    'action': 'restore observation access; health is unknown'})

        net_delta = len(issue_deltas['newly_resolved']) - len(issue_deltas['newly_opened'])

        return {
            'recommendations': recommendations,
            'net_issues_delta': net_delta,
        }

    def _update_memory(self, observation, optimization):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """INSERT INTO infra_observations
               (timestamp, disk_free_gb, disk_pct_used, launchd_failing_count,
                launchd_failing_labels, cron_missing_count, cron_missing_paths)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                observation['timestamp'],
                observation['disk_free_gb'],
                observation['disk_pct_used'],
                None if 'launchd' in observation.get('errors', {}) else len(observation['launchd_failing']),
                json.dumps(observation['launchd_failing']),
                None if 'cron' in observation.get('errors', {}) else len(observation['cron_missing']),
                json.dumps(observation['cron_missing']),
            ),
        )
        c.execute(
            "INSERT OR REPLACE INTO daemon_state (key, value, updated_at) VALUES (?, ?, ?)",
            ('last_observation', json.dumps(observation), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()


if __name__ == '__main__':
    daemon = IntelligentV6Daemon()
    result = daemon.autonomy_loop_with_intelligence()

    print("INFRASTRUCTURE HEALTH CYCLE RECORDED")
    print("Observation errors:", result["observation"]["errors"])
    print(f"Disk free: {result['observation']['disk_free_gb']}GB "
          f"({result['observation']['disk_pct_used']}% used)")
    print(f"LaunchAgents failing: {len(result['observation']['launchd_failing'])}")
    print(f"Cron entries with missing scripts: {len(result['observation']['cron_missing'])}")
    print(f"Net issues resolved this cycle: {result['performance_delta']}")
    for d in result['decisions_made']:
        print(f"  - [{d['issue']}] {d['detail']} -> {d['action']}")
