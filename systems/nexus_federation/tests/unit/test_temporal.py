"""UNIT tests: temporal classification pure functions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from state.temporal import (
    EXPIRED_THRESHOLD,
    MAX_CLOCK_SKEW,
    STALE_THRESHOLD,
    TemporalClassification,
    classify_age_only,
    classify_incoming_report,
)

NOW = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)


def _ts(offset: timedelta) -> str:
    return (NOW + offset).isoformat()


def test_first_report_ever_is_current():
    d = classify_incoming_report(
        incoming_timestamp=_ts(timedelta(0)),
        incoming_cycle_id="c1",
        prior_accepted_timestamp=None,
        prior_accepted_cycle_id=None,
        now=NOW,
    )
    assert d.classification == TemporalClassification.CURRENT
    assert d.accept is True


def test_newer_report_is_current():
    d = classify_incoming_report(
        incoming_timestamp=_ts(timedelta(0)),
        incoming_cycle_id="c2",
        prior_accepted_timestamp=_ts(-timedelta(minutes=10)),
        prior_accepted_cycle_id="c1",
        now=NOW,
    )
    assert d.classification == TemporalClassification.CURRENT


def test_older_report_is_out_of_order_and_rejected():
    d = classify_incoming_report(
        incoming_timestamp=_ts(-timedelta(minutes=10)),
        incoming_cycle_id="c2",
        prior_accepted_timestamp=_ts(timedelta(0)),
        prior_accepted_cycle_id="c1",
        now=NOW,
    )
    assert d.classification == TemporalClassification.OUT_OF_ORDER
    assert d.accept is False


def test_duplicate_cycle_id_is_idempotent_accept():
    d = classify_incoming_report(
        incoming_timestamp=_ts(timedelta(0)),
        incoming_cycle_id="same-cycle",
        prior_accepted_timestamp=_ts(timedelta(0)),
        prior_accepted_cycle_id="same-cycle",
        now=NOW,
    )
    assert d.classification == TemporalClassification.DUPLICATE
    assert d.accept is True


def test_stale_report_still_accepted_but_flagged():
    d = classify_incoming_report(
        incoming_timestamp=_ts(-(STALE_THRESHOLD + timedelta(minutes=1))),
        incoming_cycle_id="c1",
        prior_accepted_timestamp=None,
        prior_accepted_cycle_id=None,
        now=NOW,
    )
    assert d.classification == TemporalClassification.STALE
    assert d.accept is True


def test_expired_report_still_accepted_but_flagged():
    d = classify_incoming_report(
        incoming_timestamp=_ts(-(EXPIRED_THRESHOLD + timedelta(minutes=1))),
        incoming_cycle_id="c1",
        prior_accepted_timestamp=None,
        prior_accepted_cycle_id=None,
        now=NOW,
    )
    assert d.classification == TemporalClassification.EXPIRED
    assert d.accept is True


def test_clock_skew_beyond_threshold_rejected():
    d = classify_incoming_report(
        incoming_timestamp=_ts(MAX_CLOCK_SKEW + timedelta(minutes=1)),
        incoming_cycle_id="c1",
        prior_accepted_timestamp=None,
        prior_accepted_cycle_id=None,
        now=NOW,
    )
    assert d.classification == TemporalClassification.CLOCK_SKEW_REJECTED
    assert d.accept is False


def test_clock_skew_within_bound_is_fine():
    d = classify_incoming_report(
        incoming_timestamp=_ts(MAX_CLOCK_SKEW - timedelta(seconds=1)),
        incoming_cycle_id="c1",
        prior_accepted_timestamp=None,
        prior_accepted_cycle_id=None,
        now=NOW,
    )
    assert d.classification != TemporalClassification.CLOCK_SKEW_REJECTED


def test_timestamp_without_timezone_rejected():
    with pytest.raises(ValueError):
        classify_incoming_report(
            incoming_timestamp="2026-08-27T12:00:00",  # no tz
            incoming_cycle_id="c1",
            prior_accepted_timestamp=None,
            prior_accepted_cycle_id=None,
            now=NOW,
        )


def test_classify_age_only_becomes_stale_over_time_without_a_new_report():
    """Proves state visibly becomes stale as wall-clock time passes, not
    just at ingest time."""
    old_ts = _ts(-(STALE_THRESHOLD + timedelta(minutes=1)))
    assert classify_age_only(old_ts, now=NOW) == TemporalClassification.STALE
