"""Daily auditor: runs IndependentAuditor against the last 24h of Observatory events.

DailyAuditor bridges the EvidenceLedger (SQLite, hash-chained) and
IndependentAuditor.audit_historical_log (which expects a JSONL file of
records with "directive" and "code_lines" keys, matching the legacy
execution-log format). It exports the relevant slice of ledger events to a
temporary JSONL file, runs the real audit against it, and records the
resulting verdict back into the ledger as a meta-event.

The legacy line-count heuristic is reported separately; it cannot verify
truth. Daily verdicts explicitly distinguish observations from verification.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from systems.engineering_studio.studio_v3.observatory.evidence_ledger import EvidenceLedger
from systems.engineering_studio.studio_v3.observatory.independent_auditor import IndependentAuditor

AUDIT_AGENT = "daily_auditor"
AUDIT_ACTION = "audit_cycle"


class DailyAuditor:
    """Audits the last 24h of Observatory events and records a verdict."""

    def __init__(
        self,
        ledger: EvidenceLedger,
        auditor: IndependentAuditor | None = None,
        window_hours: int = 24,
    ):
        self.ledger = ledger
        self.auditor = auditor or IndependentAuditor()
        self.window_hours = window_hours

    def _window_start(self, now: datetime | None = None) -> datetime:
        now = now or datetime.now(timezone.utc)
        return now - timedelta(hours=self.window_hours)

    def _events_to_audit_log(self, events: list[dict]) -> list[dict]:
        """Only explicit line-count claims feed the legacy heuristic.

        stdout length and historical summary replays are not code changes.
        Even explicit counts are claims, not independently verified facts.
        """
        rows = []
        for ev in events:
            if ev.get('action') in (AUDIT_ACTION, 'alert_fired'):
                continue
            output = ev.get('output_data')
            if not isinstance(output, dict):
                continue
            value = output.get('code_lines')
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                rows.append({'directive': ev.get('action') or ev.get('agent'),
                             'code_lines': value, 'event_id': ev.get('event_id')})
        return rows

    def audit_last_24h(self, now: datetime | None = None) -> dict:
        """Run the real audit over the last `window_hours` of events.

        Returns the verdict dict from IndependentAuditor.audit_historical_log,
        augmented with window bounds and event_count, and records a meta-event
        in the ledger holding this verdict.
        """
        chain_ok, bad_id = self.ledger.verify_chain()
        if not chain_ok:
            raise RuntimeError(f"Evidence chain failed at {bad_id}; audit cannot attest integrity")
        window_start = self._window_start(now)
        window_end = now or datetime.now(timezone.utc)

        # EvidenceLedger.query_events only supports a lower bound ("since"),
        # so apply the upper bound client-side. This matters whenever a
        # cycle is run with an explicit past `now` (e.g. tests, backfills);
        # in normal operation window_end is "now" so this is a no-op.
        events = [
            e
            for e in self.ledger.query_events(since=window_start.isoformat())
            if e["timestamp"] <= window_end.isoformat()
            and e.get("action") not in (AUDIT_ACTION, "alert_fired")
        ]

        rows = self._events_to_audit_log(events)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as tmp:
            for row in rows:
                tmp.write(json.dumps(row) + "\n")
            tmp_path = tmp.name

        try:
            if rows:
                result = self.auditor.audit_historical_log(tmp_path, sample_size=max(len(rows), 1000))
            else:
                # No events in window: nothing to audit. Report this
                # honestly rather than fabricating a verdict.
                result = {
                    "entries_analyzed": 0,
                    "unique_directives": 0,
                    "directives_with_constant_code_lines": 0,
                    "directives_with_variable_code_lines": 0,
                    "verdict": "NO_DATA",
                    "evidence": {},
                }
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        result['heuristic_verdict'] = result['verdict']
        result['chain_integrity'] = 'PASS'
        result['scope'] = 'ledger integrity and recorded observations; not proof of genuine work, returns, learning, or scientific validity'
        observations = [e for e in events if isinstance(e.get('output_data'), dict)
                        and e['output_data'].get('measurement_kind') == 'operational_observation']
        failures = []
        for ev in observations:
            recorded = ev['output_data'].get('result', {})
            observation = recorded.get('observation', {})
            analysis = recorded.get('analysis', {})
            if (observation.get('errors') or analysis.get('issues')
                    or analysis.get('opportunities')):
                failures.append(ev['event_id'])
        result['observations_recorded'] = len(observations)
        result['observations_needing_review'] = failures
        if not events:
            result['verdict'] = 'NO_DATA'
        elif failures or result['heuristic_verdict'] == 'LIKELY_FABRICATED':
            result['verdict'] = 'REVIEW_REQUIRED'
        elif len(observations) == len(events):
            result['verdict'] = 'OBSERVATIONS_RECORDED'
        else:
            result['verdict'] = 'INCONCLUSIVE'
        result["window_start"] = window_start.isoformat()
        result["window_end"] = window_end.isoformat()
        result["event_count"] = len(events)

        self.ledger.record_event(
            agent=AUDIT_AGENT,
            action=AUDIT_ACTION,
            input_data={
                "window_start": result["window_start"],
                "window_end": result["window_end"],
                "event_count": result["event_count"],
            },
            output_data=result,
        )

        return result

    def get_previous_verdict(self, before_event_id: str | None = None) -> str | None:
        """Return the verdict from the most recent prior audit_cycle event,
        or None if this is the first audit run.
        """
        events = self.ledger.query_events(agent=AUDIT_AGENT, action=AUDIT_ACTION)
        if before_event_id is not None:
            events = [e for e in events if e["event_id"] != before_event_id]
        if not events:
            return None
        last = events[-1]
        output = last.get("output_data") or {}
        return output.get("verdict")
