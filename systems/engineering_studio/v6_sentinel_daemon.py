"""
Sentinel Investment System - REAL FINANCIAL SIGNAL DAEMON
Observes actual pattern-performance data computed by the scalper/labs pipeline
(~/.local/logs/scalpers/scalper_data.db, labs.db). No random numbers, no fixed
"learned strategy" dictionaries -- every metric is measured from real trades/signals.
"""

import json
import math
from contextlib import closing
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

try:
    from .operational_evidence import record_cycle
except ImportError:
    from operational_evidence import record_cycle

HOME = Path.home()


class SentinelAutonomousDaemon:
    def __init__(self, runtime_path=None):
        self.runtime_path = Path(runtime_path) if runtime_path else Path(__file__).resolve().parent / "runtime"
        self.runtime_path.mkdir(parents=True, exist_ok=True)
        self.sentinel_db_path = self.runtime_path / "sentinel_financial.db"
        self.scalper_db_path = HOME / ".local/logs/scalpers/scalper_data.db"
        self.labs_db_path = HOME / ".local/logs/scalpers/labs.db"
        self._init_database()

    def _init_database(self):
        conn = sqlite3.connect(self.sentinel_db_path)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS pattern_snapshots (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            pattern_name TEXT,
            total_occurrences INTEGER,
            win_rate REAL,
            sharpe REAL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS cycle_history (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            avg_win_rate REAL,
            avg_win_rate_delta REAL,
            fresh_signal_count INTEGER,
            unique_assets INTEGER
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS sentinel_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        )""")
        conn.commit()
        conn.close()

    def autonomy_loop_financial(self):
        observation = self._observe_markets()
        analysis = self._analyze_opportunities(observation)
        delta = self._learn(observation)
        optimization = self._summarize(analysis, delta)
        self._update_memory(observation, optimization)

        result = {
            'observation': observation,
            'analysis': analysis,
            'strategies_applied': optimization['applied'],
            'avg_win_rate_delta': optimization['avg_win_rate_delta'],
            'financial_delta': None,  # no measured P&L or executed trade
            'execution_mode': 'observe_only',
            'decisions_made': optimization['decisions_made'],
        }

        result["evidence_event_id"] = record_cycle(self.runtime_path, "sentinel", result)
        return result

    def _observe_markets(self):
        """OBSERVE: real pattern performance + real live signal freshness."""
        patterns = []
        errors = {}
        invalid_patterns = 0
        try:
            with closing(sqlite3.connect(self.scalper_db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as conn:
                for row in conn.execute("SELECT pattern_name, total_occurrences, win_rate, sharpe FROM pattern_summary WHERE total_occurrences >= 20"):
                    if (not isinstance(row[2], (int, float)) or not math.isfinite(row[2])
                            or not 0 <= row[2] <= 1 or not isinstance(row[3], (int, float))
                            or not math.isfinite(row[3])):
                        invalid_patterns += 1
                        continue
                    patterns.append({'pattern': row[0], 'occurrences': row[1], 'win_rate': row[2], 'sharpe': row[3]})
        except (sqlite3.Error, OSError) as exc:
            errors['patterns'] = str(exc)

        fresh_signal_count = unique_assets = latest_signal_age_s = None
        try:
            with closing(sqlite3.connect(self.labs_db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as conn:
                # Normalize ISO T/space/offset formats and exclude future timestamps.
                now = datetime.now(timezone.utc).isoformat()
                fresh_signal_count, unique_assets = conn.execute(
                    "SELECT COUNT(*), COUNT(DISTINCT asset) FROM lab_signals "
                    "WHERE julianday(ts) BETWEEN julianday(?) - 1.0/24 AND julianday(?)", (now, now)
                ).fetchone()
                age = conn.execute("SELECT (julianday(?) - MAX(julianday(ts))) * 86400 FROM lab_signals", (now,)).fetchone()[0]
                latest_signal_age_s = age
                if age is not None and age < 0:
                    errors['signal_clock'] = 'future-dated signals present'
                invalid_ts = conn.execute("SELECT COUNT(*) FROM lab_signals WHERE julianday(ts) IS NULL").fetchone()[0]
                if invalid_ts:
                    errors['signal_timestamps'] = f'{invalid_ts} unparseable timestamps'
        except (sqlite3.Error, OSError) as exc:
            errors['signals'] = str(exc)

        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'patterns_tracked': len(patterns), 'patterns': patterns,
            'invalid_pattern_metrics': invalid_patterns,
            'fresh_signal_count_1h': fresh_signal_count,
            'unique_assets_1h': unique_assets,
            'latest_signal_age_seconds': latest_signal_age_s,
            'errors': errors,
            'provenance': {'patterns': str(self.scalper_db_path), 'signals': str(self.labs_db_path)},
            'measurement_scope': 'upstream database metrics; not independently verified trades or returns',
        }

    def _analyze_opportunities(self, observation):
        """ANALYZE: real thresholds against real win_rate/sharpe values."""
        strong = [p for p in observation['patterns'] if p['win_rate'] > 0.55 and p['sharpe'] > 0.3]
        weak = [p for p in observation['patterns'] if p['win_rate'] < 0.45]

        opportunities = ['observation_failed:' + key for key in observation.get('errors', {})]
        if observation['invalid_pattern_metrics']:
            opportunities.append('invalid_pattern_metrics')
        if not observation['patterns']:
            opportunities.append('no_evaluable_patterns')
        if observation['fresh_signal_count_1h'] == 0:
            opportunities.append('no_recent_signals')
        if strong:
            opportunities.append(f"{len(strong)}_patterns_outperforming")
        if weak:
            opportunities.append(f"{len(weak)}_patterns_underperforming")
        if observation['latest_signal_age_seconds'] is not None and observation['latest_signal_age_seconds'] > 3600:
            opportunities.append('signals_stale')

        return {
            'opportunities': opportunities,
            'strong_patterns': [p['pattern'] for p in strong],
            'weak_patterns': [p['pattern'] for p in weak],
        }

    def _learn(self, observation):
        """LEARN: store this cycle's snapshot, compute a real delta vs the previous cycle."""
        conn = sqlite3.connect(self.sentinel_db_path)
        c = conn.cursor()

        now = observation['timestamp']
        for p in observation['patterns']:
            c.execute(
                "INSERT INTO pattern_snapshots (timestamp, pattern_name, total_occurrences, win_rate, sharpe) "
                "VALUES (?, ?, ?, ?, ?)",
                (now, p['pattern'], p['occurrences'], p['win_rate'], p['sharpe']),
            )

        avg_win_rate = (
            sum(p['win_rate'] for p in observation['patterns']) / len(observation['patterns'])
            if observation['patterns'] else None
        )

        c.execute("SELECT value FROM sentinel_state WHERE key = 'avg_win_rate'")
        row = c.fetchone()
        previous_avg = float(row[0]) if row else None

        delta = (avg_win_rate - previous_avg) if (avg_win_rate is not None and previous_avg is not None) else None

        conn.commit()
        conn.close()

        return {'avg_win_rate': avg_win_rate, 'avg_win_rate_delta': delta, 'previous_avg': previous_avg}

    def _summarize(self, analysis, delta):
        """OPTIMIZE: honest decisions grounded in the real strong/weak pattern lists."""
        decisions = []
        for name in analysis['strong_patterns']:
            decisions.append({'pattern': name, 'action': 'retain_in_active_set', 'reason': 'win_rate>0.55 and sharpe>0.3'})
        for name in analysis['weak_patterns']:
            decisions.append({'pattern': name, 'action': 'flag_for_review', 'reason': 'win_rate<0.45'})

        return {
            'applied': False,
            'decisions_made': decisions,
            'avg_win_rate_delta': round(delta['avg_win_rate_delta'], 5) if delta['avg_win_rate_delta'] is not None else None,
            'avg_win_rate': delta['avg_win_rate'],
        }

    def _update_memory(self, observation, optimization):
        conn = sqlite3.connect(self.sentinel_db_path)
        c = conn.cursor()
        c.execute(
            "INSERT INTO cycle_history (timestamp, avg_win_rate, avg_win_rate_delta, fresh_signal_count, unique_assets) "
            "VALUES (?, ?, ?, ?, ?)",
            (observation['timestamp'], optimization['avg_win_rate'], optimization['avg_win_rate_delta'],
             observation['fresh_signal_count_1h'], observation['unique_assets_1h']),
        )
        if optimization['avg_win_rate'] is not None:
            c.execute(
                "INSERT OR REPLACE INTO sentinel_state (key, value, updated_at) VALUES (?, ?, ?)",
                ('avg_win_rate', str(optimization['avg_win_rate']), datetime.now(timezone.utc).isoformat()),
            )
        conn.commit()
        conn.close()


if __name__ == '__main__':
    daemon = SentinelAutonomousDaemon()
    result = daemon.autonomy_loop_financial()

    print("SENTINEL UPSTREAM SIGNAL OBSERVATION RECORDED (NO TRADES EXECUTED)")
    print("Observation errors:", result["observation"]["errors"])
    print(f"Patterns tracked: {result['observation']['patterns_tracked']}")
    print(f"Fresh signals (1h): {result['observation']['fresh_signal_count_1h']} "
          f"across {result['observation']['unique_assets_1h']} assets")
    print(f"Avg win rate delta vs last cycle: {result['avg_win_rate_delta']}")
    print(f"Decisions made: {len(result['decisions_made'])}")
    for d in result['decisions_made'][:5]:
        print(f"  - {d['pattern']}: {d['action']} ({d['reason']})")
