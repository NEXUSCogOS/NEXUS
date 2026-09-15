"""Append observed cycles to Studio's ledger. Never writes to source databases."""
from __future__ import annotations

import hashlib
from pathlib import Path
try:
    from .studio_v3.observatory.evidence_ledger import EvidenceLedger
except ImportError:
    from studio_v3.observatory.evidence_ledger import EvidenceLedger


def record_cycle(runtime_path, agent, result):
    ledger = EvidenceLedger(Path(runtime_path) / 'operational_evidence.sqlite3')
    try:
        source = Path(__file__).parent / {
            'infra': 'v6_intelligent_daemon.py',
            'datai': 'v6_datai_daemon.py',
            'sentinel': 'v6_sentinel_daemon.py',
        }[agent]
        return ledger.record_event(
            agent=agent, action='observation_cycle',
            input_data={'implementation_sha256': hashlib.sha256(source.read_bytes()).hexdigest()},
            output_data={
                'measurement_kind': 'operational_observation',
                'execution_mode': 'observe_only',
                'actions_executed': [],
                'result': result,
            },
        )
    finally:
        ledger.close()
