"""
DatAI System - REAL DATA LANDSCAPE HEALTH DAEMON
Observes actual size, row counts, and freshness of NEXUS's real data stores.
No random record counts or simulated efficiency gains -- every value is a
real filesystem stat or a real SQL COUNT/MAX(mtime).
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

try:
    from .operational_evidence import record_cycle
except ImportError:
    from operational_evidence import record_cycle

HOME = Path.home()

# Real data stores this daemon actually tracks.
DATA_SOURCES = {
    'scalper_binance_logs': HOME / ".local/logs/scalpers/binance",
    'scalper_vn_logs': HOME / ".local/logs/scalpers/vn",
    'scalper_data_db': HOME / ".local/logs/scalpers/scalper_data.db",
    'labs_db': HOME / ".local/logs/scalpers/labs.db",
    'sentinel_logs': HOME / ".local/logs/sentinels",
}


class DatAIDaemon:
    def __init__(self, runtime_path=None):
        self.runtime_path = Path(runtime_path) if runtime_path else Path(__file__).resolve().parent / "runtime"
        self.runtime_path.mkdir(parents=True, exist_ok=True)
        self.datai_db_path = self.runtime_path / "datai_analytics.db"
        self._init_database()

    def _init_database(self):
        conn = sqlite3.connect(self.datai_db_path)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS source_snapshots (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            source TEXT,
            size_mb REAL,
            file_count INTEGER,
            newest_mtime_age_hours REAL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS datai_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        )""")
        conn.commit()
        conn.close()

    def autonomy_loop_datai(self):
        observation = self._observe_data()
        analysis = self._analyze_data(observation)
        delta = self._learn(observation)
        optimization = self._summarize(analysis, delta)
        self._update_memory(observation, optimization)

        result = {
            'observation': observation,
            'analysis': analysis,
            'patterns_applied': optimization['applied'],
            'size_delta_mb': optimization['size_delta_mb'],
            'efficiency_gain': None,
            'execution_mode': 'observe_only',
            'decisions_made': optimization['decisions_made'],
        }

        result["evidence_event_id"] = record_cycle(self.runtime_path, "datai", result)
        return result

    def _observe_data(self):
        """OBSERVE: real du-style size, real file counts, real newest-file age per source."""
        source_stats = {}
        errors = {}
        now = datetime.now().timestamp()

        for name, path in DATA_SOURCES.items():
            try:
                if path.is_file():
                    # SQLite WAL writes may not touch the main DB mtime.
                    files = [path] + [p for p in (Path(str(path) + '-wal'), Path(str(path) + '-shm')) if p.exists()]
                elif path.is_dir():
                    files = [f for f in path.rglob('*') if f.is_file()]
                else:
                    source_stats[name] = None
                    continue
                stats = []
                for f in files:
                    try:
                        stats.append(f.stat())
                    except FileNotFoundError:
                        continue  # concurrent retention or WAL checkpoint
                size_mb = sum(st.st_size for st in stats) / (1024 * 1024)
                newest_age_hours = (now - max(st.st_mtime for st in stats)) / 3600 if stats else None
                source_stats[name] = {
                    'size_mb': round(size_mb, 2), 'file_count': len(stats),
                    'newest_mtime_age_hours': round(newest_age_hours, 2) if newest_age_hours is not None else None,
                }
            except OSError as exc:
                errors[name] = str(exc)
                source_stats[name] = None

        total_mb = sum(s['size_mb'] for s in source_stats.values() if s)

        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'sources_scanned': len(DATA_SOURCES),
            'errors': errors,
            'measurement_scope': 'filesystem activity only; mtime does not prove market data freshness',
            'source_stats': source_stats,
            'total_data_mb': round(total_mb, 2),
        }

    def _analyze_data(self, observation):
        """ANALYZE: real staleness (>48h since newest file) and real size thresholds."""
        stale = [
            name for name, s in observation['source_stats'].items()
            if s and s['newest_mtime_age_hours'] is not None and s['newest_mtime_age_hours'] > 48
        ]
        large = [
            name for name, s in observation['source_stats'].items()
            if s and s['size_mb'] > 5000
        ]
        missing = [name for name, s in observation['source_stats'].items() if s is None]

        issues = []
        if stale:
            issues.append('stale_data_detected')
        if large:
            issues.append('retention_candidate')
        if missing:
            issues.append('source_missing')

        return {'issues': issues, 'stale_sources': stale, 'large_sources': large, 'missing_sources': missing}

    def _learn(self, observation):
        """LEARN: real delta in total data size vs the last recorded cycle."""
        conn = sqlite3.connect(self.datai_db_path)
        c = conn.cursor()

        c.execute("SELECT value FROM datai_state WHERE key = 'total_data_mb'")
        row = c.fetchone()
        previous_total = float(row[0]) if row else None
        delta = (observation['total_data_mb'] - previous_total) if previous_total is not None and not observation.get("errors") else None

        conn.close()
        return {'previous_total_mb': previous_total, 'size_delta_mb': delta}

    def _summarize(self, analysis, delta):
        """OPTIMIZE: honest recommendations, not fabricated efficiency percentages."""
        decisions = []
        for name in analysis['stale_sources']:
            decisions.append({'source': name, 'action': 'check_ingestion_pipeline', 'reason': 'no new file in >48h'})
        for name in analysis['large_sources']:
            decisions.append({'source': name, 'action': 'run_retention', 'reason': 'exceeds 5GB'})
        for name in analysis['missing_sources']:
            decisions.append({'source': name, 'action': 'verify_path', 'reason': 'path does not exist'})

        return {
            'applied': False,
            'decisions_made': decisions,
            'size_delta_mb': round(delta['size_delta_mb'], 2) if delta['size_delta_mb'] is not None else None,
        }

    def _update_memory(self, observation, optimization):
        conn = sqlite3.connect(self.datai_db_path)
        c = conn.cursor()
        for name, s in observation['source_stats'].items():
            if s:
                c.execute(
                    "INSERT INTO source_snapshots (timestamp, source, size_mb, file_count, newest_mtime_age_hours) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (observation['timestamp'], name, s['size_mb'], s['file_count'], s['newest_mtime_age_hours']),
                )
        c.execute(
            "INSERT OR REPLACE INTO datai_state (key, value, updated_at) VALUES (?, ?, ?)",
            ('total_data_mb', str(observation['total_data_mb']), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()


if __name__ == '__main__':
    daemon = DatAIDaemon()
    result = daemon.autonomy_loop_datai()

    print("DATAI LANDSCAPE HEALTH CYCLE COMPLETE")
    print(f"Sources scanned: {result['observation']['sources_scanned']}")
    print(f"Total data tracked: {result['observation']['total_data_mb']} MB")
    print(f"Size delta vs last cycle: {result['size_delta_mb']} MB")
    for name, s in result['observation']['source_stats'].items():
        if s:
            print(f"  {name}: {s['size_mb']}MB, {s['file_count']} files, "
                  f"newest {s['newest_mtime_age_hours']}h ago")
        else:
            print(f"  {name}: MISSING")
    print(f"Decisions made: {len(result['decisions_made'])}")
    for d in result['decisions_made']:
        print(f"  - [{d['source']}] {d['action']} ({d['reason']})")
