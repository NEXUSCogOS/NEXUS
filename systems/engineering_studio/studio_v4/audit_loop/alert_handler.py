"""Alert handler: detects verdict changes and fires alerts on fabrication.

Alerts fire when:
  - the verdict flips from a non-fabricated state to LIKELY_FABRICATED
  - the verdict is LIKELY_FABRICATED on the very first audit (no prior verdict)
  - consistency degrades: previous verdict was LIKELY_REAL and current is MIXED
    or LIKELY_FABRICATED (a "consistency drop")

Alerts are recorded to the Observatory ledger (so they're part of the
tamper-evident chain) and also emitted to stdout by default. An optional
`notifier` callable can be supplied for email/webhook delivery; it is never
required, so alerting degrades gracefully to stdout-only.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Callable

from systems.engineering_studio.studio_v3.observatory.evidence_ledger import EvidenceLedger

ALERT_AGENT = "alert_handler"
ALERT_ACTION = "alert_fired"

FABRICATED_VERDICTS = {"LIKELY_FABRICATED"}
DEGRADED_VERDICTS = {"MIXED", "LIKELY_FABRICATED"}


class AlertHandler:
    """Detects verdict changes across audit cycles and fires alerts."""

    def __init__(
        self,
        ledger: EvidenceLedger,
        notifier: Callable[[dict], None] | None = None,
    ):
        self.ledger = ledger
        self.notifier = notifier

    def check_verdict_change(self, previous_verdict: str | None, current_verdict: str) -> dict:
        """Determine whether a change from previous_verdict -> current_verdict
        warrants an alert. Returns a dict describing the decision; does not
        fire the alert itself.
        """
        should_alert = False
        reason = None

        if current_verdict in {'REVIEW_REQUIRED', 'NO_DATA', 'INCONCLUSIVE'}:
            should_alert = True
            reason = 'verification_requires_attention'
        elif current_verdict in FABRICATED_VERDICTS:
            should_alert = True
            reason = "fabrication_detected"
        elif (
            previous_verdict == "LIKELY_REAL"
            and current_verdict in DEGRADED_VERDICTS
            and current_verdict not in FABRICATED_VERDICTS
        ):
            should_alert = True
            reason = "consistency_drop"
        elif previous_verdict is not None and previous_verdict != current_verdict:
            # Any other verdict change is logged as informational, not alerted.
            should_alert = False
            reason = "verdict_changed_non_critical"

        return {
            "previous_verdict": previous_verdict,
            "current_verdict": current_verdict,
            "should_alert": should_alert,
            "reason": reason,
        }

    def fire_alert(self, previous_verdict: str | None, current_verdict: str, details: dict | None = None) -> dict:
        """Record and emit an alert. Called only when check_verdict_change
        (or the caller's own logic) has determined an alert is warranted.
        """
        alert = {
            "previous_verdict": previous_verdict,
            "current_verdict": current_verdict,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        }

        self.ledger.record_event(
            agent=ALERT_AGENT,
            action=ALERT_ACTION,
            input_data={"previous_verdict": previous_verdict, "current_verdict": current_verdict},
            output_data=alert,
        )

        message = (
            f"[ALERT] Audit verdict changed: {previous_verdict!r} -> {current_verdict!r} "
            f"at {alert['timestamp']}"
        )
        print(message, file=sys.stderr)

        if self.notifier is not None:
            self.notifier(alert)

        return alert

    def process(self, previous_verdict: str | None, current_verdict: str, details: dict | None = None) -> dict | None:
        """Convenience: check and fire in one call. Returns the fired alert
        dict, or None if no alert was warranted.
        """
        decision = self.check_verdict_change(previous_verdict, current_verdict)
        if decision["should_alert"]:
            return self.fire_alert(previous_verdict, current_verdict, details=details)
        return None
