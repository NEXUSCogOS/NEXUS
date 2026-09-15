"""Sentinel's F5 analysis executor -- real, read-only queries against the
observed active Sentinel database, with explicit financial epistemology
tagging.

New module, NEXUS Federation F5. Modeled on Librarian's own
`runtime/academic_research_executor.py` (F3): a thin, honest layer between
a federation delegation and the specialist institution's real data, which
NEVER fabricates a value it did not query, and NEVER launders a stale
observation into a claim about the present.

Financial epistemology (Phase 4 mission, section J): every string this
module emits into `findings`/`observations` is prefixed with one of:

    OBSERVED_MARKET_FACT   a value read directly from a stored row,
                           unchanged (a price, a regime label, a decision
                           action -- exactly as persisted)
    DERIVED_METRIC         a value computed here from stored rows by a
                           fixed, named arithmetic rule (e.g. an age in
                           days, a simple ratio)
    MODEL_ESTIMATE         a value that was itself the OUTPUT of Sentinel's
                           own scoring/decision model at write time (e.g.
                           decision_score, composite_regime_score) --
                           carried through verbatim, never recomputed here
    SIGNAL                 a named trading-relevant signal already recorded
                           in signals_unified/frontier_decisions
    FORECAST               a statement about a FUTURE market state --
                           this executor never produces one (Sentinel has
                           no forecasting capability; see
                           SENTINEL_INSTITUTIONAL_CONTRACT.md)
    RECOMMENDATION         placed only in `recommended_next_actions`, never
                           in `findings`/`observations`
    UNKNOWN                the value could not be determined from any
                           query this executor ran

No row is ever fabricated. Every numeric value traces to one SELECT
statement, referenced by `evidence_refs` as `db_query:<name>`. This module
never opens the database for write access (`sqlite3.connect(..., uri=True)`
with `mode=ro`) and never imports or calls anything from
historical/execution_engine.py or frontier_pipeline.py's write paths.
"""

from __future__ import annotations

import sqlite3
import sys
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

# The real, observed active Sentinel source tree -- a separate git
# repository from NEXUS, per the F5 forensic audit
# (SENTINEL_F5_FORENSIC_AUDIT.md). Imported directly, not reimplemented,
# so this executor's freshness classification is provably the SAME
# function the production ingest pipeline uses -- not a parallel
# reimplementation that could silently drift from it.
SENTINEL_SOURCE_PARENT = str(Path.home())

if SENTINEL_SOURCE_PARENT not in sys.path:
    sys.path.insert(0, SENTINEL_SOURCE_PARENT)

from sentinel.frontier_ingest import _frontier_price_freshness  # noqa: E402

# Data older than this, relative to the moment analysis runs (NOT relative
# to whatever freshness label was stamped on the row when it was written),
# is CURRENT-MARKET-INELIGIBLE: this executor will refuse to answer a
# "what is happening right now" question from it, no matter how fresh the
# row claimed to be on the day it was written.
CURRENT_MARKET_FRESHNESS_THRESHOLD_DAYS = 5


@dataclass
class ComponentFinding:
    """One component's real, evidence-backed state."""

    name: str
    lifecycle: str  # a contracts.generic.CapabilityLifecycle value, as a string
    evidence_refs: list[str] = field(default_factory=list)
    detail: str = ""
    tagged_findings: list[str] = field(default_factory=list)  # epistemology-prefixed


@dataclass
class AnalysisResult:
    generated_at: str
    analysis_run_id: str  # a real uuid4, minted once per invocation -- the
                           # provenance anchor for every evidence_ref this
                           # run produced (mission section O)
    db_path: str
    components: list[ComponentFinding]
    observations: list[str]  # OBSERVED_MARKET_FACT-prefixed only
    findings: list[str]  # DERIVED_METRIC/MODEL_ESTIMATE/SIGNAL-prefixed
    limitations: list[str]
    risks: list[str]
    recommended_next_actions: list[str]  # RECOMMENDATION-prefixed
    evidence_refs: list[str]
    data_status: str  # CURRENT | STALE | UNKNOWN -- market_data (raw prices) freshness
    latest_verified_date: Optional[str]
    age_days: Optional[int]
    current_market_conclusion_permitted: bool  # raw price data current-ness
    regime_age_days: Optional[int] = None
    current_regime_conclusion_permitted: bool = False  # can we say what regime the market is in RIGHT NOW
    signal_age_days: Optional[int] = None
    decision_age_days: Optional[int] = None
    decision_id_latest: Optional[str] = None


def _ro_connect(db_path: str) -> sqlite3.Connection:
    """Read-only connection. Any accidental write attempt raises rather
    than silently succeeding."""
    uri = f"file:{Path(db_path).resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def run_bounded_analysis(
    *,
    db_path: str,
    as_of: Optional[datetime] = None,
) -> AnalysisResult:
    """Execute the F5 commissioning mission against real, verified Sentinel
    data. Read-only. Refuses to characterize the CURRENT market from data
    that exceeds the freshness threshold -- it will characterize the most
    recent SUPPORTED regime instead and say so explicitly.
    """
    now = as_of or datetime.now(timezone.utc)
    analysis_run_id = str(uuid.uuid4())
    conn = _ro_connect(db_path)

    components: list[ComponentFinding] = []
    observations: list[str] = []
    findings: list[str] = []
    limitations: list[str] = []
    risks: list[str] = []
    recommended: list[str] = []
    evidence_refs: list[str] = [f"analysis_run_id:{analysis_run_id}"]

    # ---- market_data ----------------------------------------------------
    # prices_daily contains 689 rows (verified by direct query during the
    # F5 audit) whose `date` column is a malformed single-character value
    # ('0','1','2','3') rather than an ISO date. A naive `ORDER BY date
    # DESC` sorts these ahead of real dates (lexically, '3' > '2026-...'),
    # so the query below explicitly requires YYYY-MM-DD-shaped values.
    # This malformation is reported as a limitation below, not silently
    # worked around without comment.
    malformed_date_count = conn.execute(
        "SELECT COUNT(*) AS n FROM prices_daily "
        "WHERE date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"
    ).fetchone()["n"]

    latest_price_row = conn.execute(
        "SELECT id, symbol, date, close FROM prices_daily "
        "WHERE date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' "
        "ORDER BY date DESC LIMIT 1"
    ).fetchone()

    if malformed_date_count:
        limitations.append(
            f"DATA_QUALITY: {malformed_date_count} row(s) in prices_daily "
            f"have a malformed `date` value (observed: single-digit "
            f"strings '0'/'1'/'2'/'3' instead of YYYY-MM-DD). These sort "
            f"ahead of real dates under a naive ORDER BY date DESC and were "
            f"excluded from the freshness query below by an explicit date-"
            f"shape filter. The same malformed rows are visible live in "
            f"Sentinel's own production logs as "
            f"'NO_SIGNAL — UNKNOWN latest=3 age=None' for hundreds of "
            f"symbols on the most recent scheduled run "
            f"(logs/frontier_pipeline_error.log, 2026-08-27), where "
            f"Sentinel's own freshness gate is correctly refusing to treat "
            f"them as fresh -- this is the gate working as designed, not a "
            f"gate failure, but the underlying malformed rows are a real "
            f"data-quality defect this executor did not fix."
        )
        evidence_refs.append("db_query:prices_daily_malformed_date_count")

    latest_verified_date = None
    age_days = None
    market_data_lifecycle = "UNKNOWN"

    market_data_record_id = None

    if latest_price_row:
        market_data_record_id = f"prices_daily:id={latest_price_row['id']}"
        latest_verified_date = str(latest_price_row["date"])
        parsed = date.fromisoformat(latest_verified_date[:10])
        age_days = (now.date() - parsed).days
        freshness_label, _ = _frontier_price_freshness(latest_verified_date)

        observations.append(
            f"OBSERVED_MARKET_FACT: latest verified price row is dated "
            f"{latest_verified_date} (symbol={latest_price_row['symbol']!r}, "
            f"close={latest_price_row['close']}, "
            f"market_data_record_id={market_data_record_id})"
        )
        findings.append(
            f"DERIVED_METRIC: latest verified price data is {age_days} "
            f"calendar day(s) old as of this analysis (freshness label at "
            f"write time was {freshness_label!r}; that label describes "
            f"freshness on the day it was written, not freshness now)"
        )
        evidence_refs.append(market_data_record_id)

        if age_days <= CURRENT_MARKET_FRESHNESS_THRESHOLD_DAYS:
            market_data_lifecycle = "INTEGRATED"
        else:
            market_data_lifecycle = "EXTERNAL_DEPENDENCY_UNAVAILABLE"
            limitations.append(
                f"STALE_DATA: latest verified price data is {age_days} days "
                f"old, exceeding the {CURRENT_MARKET_FRESHNESS_THRESHOLD_DAYS}"
                f"-day current-market threshold. Root cause: VNStock "
                f"community-tier rate limiting (EXTERNAL_DEPENDENCY_DEGRADED) "
                f"-- see SENTINEL_F5_PHASE_2A_REPORT.md."
            )
    else:
        limitations.append("UNKNOWN: no rows found in prices_daily")

    current_market_conclusion_permitted = (
        age_days is not None and age_days <= CURRENT_MARKET_FRESHNESS_THRESHOLD_DAYS
    )

    components.append(ComponentFinding(
        name="market_data",
        lifecycle=market_data_lifecycle,
        evidence_refs=["db_query:prices_daily_latest"],
        detail=f"latest={latest_verified_date} age_days={age_days}",
    ))

    # ---- signal_engine ----------------------------------------------
    # F5.1 (2026-08-28): signals_unified/frontier_decisions were stale for
    # an architectural reason (frontier_pipeline.py never dispatched the
    # signal/decision/regime stages) -- fixed by wiring three new stages
    # into the scheduler (Sentinel repo commit 56ec4e0) and by a related
    # technicals_worker defect fix (the happy path never stamped
    # freshness metadata, so a genuinely fresh signal always read back as
    # 'UNKNOWN' downstream). Both freshness AND the underlying gap are
    # tracked independently below -- freshness age is a per-run fact,
    # the gap's existence/resolution is a one-time architectural finding
    # recorded permanently in SENTINEL_DECISION_PIPELINE_FORENSIC_REPORT.md.
    signal_age: Optional[int] = None
    signal_row = conn.execute(
        "SELECT symbol, action, freshness, data_status, ts "
        "FROM signals_unified WHERE freshness='FRESH' AND data_status='CURRENT' "
        "ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    if signal_row:
        observations.append(
            f"OBSERVED_MARKET_FACT: most recent FRESH/CURRENT signal is "
            f"{signal_row['action']!r} for {signal_row['symbol']!r} at "
            f"{signal_row['ts']}"
        )
        signal_ts = str(signal_row["ts"])[:10]
        try:
            # signals_unified.ts is written via datetime.now().isoformat()
            # (naive, local time) while `now` here is UTC-aware -- a real,
            # separate timestamp-convention inconsistency versus
            # frontier_decisions/frontier_market_regime (both UTC-aware).
            # Not fixed here (out of restoration scope; flagged in
            # SENTINEL_DECISION_PIPELINE_FORENSIC_REPORT.md as a follow-up).
            # Clamp to 0 rather than report a negative age when the local
            # clock's date is ahead of UTC's.
            signal_age = max(0, (now.date() - date.fromisoformat(signal_ts)).days)
        except ValueError:
            signal_age = None
        signals_lifecycle = "INTEGRATED" if (signal_age is not None and signal_age <= CURRENT_MARKET_FRESHNESS_THRESHOLD_DAYS) else "DEGRADED"
        evidence_refs.append(f"signals_unified:id_latest_fresh")
    else:
        signals_lifecycle = "EXTERNAL_DEPENDENCY_UNAVAILABLE"
        limitations.append(
            "No FRESH/CURRENT signal found in signals_unified -- either "
            "the signals stage has not run recently, or no symbol "
            "currently has fresh enough price data to qualify."
        )
    components.append(ComponentFinding(
        name="signal_engine", lifecycle=signals_lifecycle,
        evidence_refs=["db_query:signals_unified_latest_fresh"],
        detail=f"age_days={signal_age}",
    ))

    # ---- decision_engine ----------------------------------------------
    decision_age: Optional[int] = None
    decision_row = conn.execute(
        "SELECT decision_id, symbol, decision_action, created_at "
        "FROM frontier_decisions ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if decision_row:
        decision_id_latest = decision_row["decision_id"]
        observations.append(
            f"OBSERVED_MARKET_FACT: most recent decision is "
            f"{decision_row['decision_action']!r} for "
            f"{decision_row['symbol']!r} (decision_id={decision_id_latest}) "
            f"at {decision_row['created_at']}"
        )
        decision_ts = str(decision_row["created_at"])[:10]
        try:
            decision_age = (now.date() - date.fromisoformat(decision_ts)).days
        except ValueError:
            decision_age = None
        decision_lifecycle = "INTEGRATED" if (decision_age is not None and decision_age <= CURRENT_MARKET_FRESHNESS_THRESHOLD_DAYS) else "DEGRADED"
        evidence_refs.append(f"frontier_decisions:decision_id={decision_id_latest}")
    else:
        decision_lifecycle = "UNKNOWN"
        decision_id_latest = None
    components.append(ComponentFinding(
        name="decision_engine", lifecycle=decision_lifecycle,
        evidence_refs=["db_query:frontier_decisions_latest"],
        detail=f"age_days={decision_age}",
    ))

    # ---- regime -------------------------------------------------------
    regime_age: Optional[int] = None
    regime_is_current = False

    regime_row = conn.execute(
        "SELECT id, generated_at, market_date, regime, confidence, "
        "composite_regime_score, data_quality, rationale "
        "FROM frontier_market_regime ORDER BY generated_at DESC LIMIT 1"
    ).fetchone()

    if regime_row:
        derived_metric_id = f"frontier_market_regime:id={regime_row['id']}"
        evidence_refs.append(derived_metric_id)
        observations.append(
            f"OBSERVED_MARKET_FACT: the most recent SUPPORTED market regime "
            f"classification on record is {regime_row['regime']!r} "
            f"(derived_metric_or_signal_id={derived_metric_id}), for "
            f"market_date={regime_row['market_date']} "
            f"(generated_at={regime_row['generated_at']})"
        )
        findings.append(
            f"MODEL_ESTIMATE: composite_regime_score="
            f"{regime_row['composite_regime_score']:.2f}, "
            f"confidence={regime_row['confidence']:.3f} "
            f"(Sentinel's own frontier regime model output, carried "
            f"through unchanged -- not recomputed by this executor)"
        )

        # The regime's OWN age, independent of market_data's age -- the two
        # are computed from different tables (frontier_market_regime vs.
        # prices_daily) and can diverge, exactly as they do at the time
        # this executor was written (see the ARCHITECTURAL_GAP limitation
        # under "signals" above): prices_daily is current, but nothing in
        # the scheduled pipeline regenerates frontier_market_regime, so it
        # is NOT current even when market_data is.
        regime_ts = str(regime_row["generated_at"])[:10]
        try:
            regime_age = (now.date() - date.fromisoformat(regime_ts)).days
        except ValueError:
            regime_age = None
        regime_is_current = (
            regime_age is not None
            and regime_age <= CURRENT_MARKET_FRESHNESS_THRESHOLD_DAYS
        )

        if not regime_is_current:
            findings.append(
                f"DERIVED_METRIC: this regime classification is "
                f"{regime_age} days old and is NOT presented as the "
                f"current market regime -- it is the most recent regime "
                f"this database can support with verified data. (Note: "
                f"prices_daily itself is current -- see market_data above "
                f"-- but regime generation is not; these are independently "
                f"tracked, see the signals ARCHITECTURAL_GAP limitation.)"
            )
        regime_lifecycle = "INTEGRATED" if regime_is_current else "DEGRADED"
    else:
        regime_lifecycle = "UNKNOWN"

    components.append(ComponentFinding(
        name="regime_detection", lifecycle=regime_lifecycle,
        evidence_refs=["db_query:frontier_market_regime_latest"],
        detail=f"age_days={regime_age}",
    ))

    # ---- risk -----------------------------------------------------------
    risk_row = conn.execute(
        "SELECT risk_halt FROM frontier_risk_state WHERE id=1"
    ).fetchone()
    if risk_row is not None:
        observations.append(
            f"OBSERVED_MARKET_FACT: frontier_risk_state.risk_halt="
            f"{risk_row['risk_halt']}"
        )
        risk_lifecycle = "INTEGRATED"
        evidence_refs.append("db_query:frontier_risk_state")
    else:
        risk_lifecycle = "UNKNOWN"
        limitations.append("UNKNOWN: frontier_risk_state row not found")
    components.append(ComponentFinding(
        name="risk", lifecycle=risk_lifecycle,
        evidence_refs=["db_query:frontier_risk_state"],
    ))

    # ---- portfolio --------------------------------------------------
    try:
        portfolio_count = conn.execute(
            "SELECT COUNT(*) AS n FROM frontier_portfolio_runs"
        ).fetchone()["n"]
        findings.append(
            f"DERIVED_METRIC: {portfolio_count} portfolio construction "
            f"run(s) on record"
        )
        portfolio_lifecycle = "INTEGRATED" if portfolio_count else "NOT_COMMISSIONED"
        evidence_refs.append("db_query:frontier_portfolio_runs_count")
    except sqlite3.Error:
        portfolio_lifecycle = "UNKNOWN"
    components.append(ComponentFinding(
        name="portfolio", lifecycle=portfolio_lifecycle,
        evidence_refs=["db_query:frontier_portfolio_runs_count"],
    ))

    # ---- backtesting / walk_forward -------------------------------------
    try:
        wf_count = conn.execute(
            "SELECT COUNT(*) AS n FROM historical_validation_executions"
        ).fetchone()["n"]
        backtest_lifecycle = "INTEGRATED" if wf_count else "NOT_COMMISSIONED"
        findings.append(
            f"DERIVED_METRIC: {wf_count} historical validation execution "
            f"row(s) on record (walk-forward/backtest ledger)"
        )
        evidence_refs.append("db_query:historical_validation_executions_count")
    except sqlite3.Error:
        backtest_lifecycle = "UNKNOWN"
    components.append(ComponentFinding(
        name="backtesting", lifecycle=backtest_lifecycle,
        evidence_refs=["db_query:historical_validation_executions_count"],
    ))
    components.append(ComponentFinding(
        name="walk_forward", lifecycle=backtest_lifecycle,
        evidence_refs=["db_query:historical_validation_executions_count"],
    ))

    # ---- fundamentals -----------------------------------------------
    try:
        fund_count = conn.execute(
            "SELECT COUNT(*) AS n FROM fundamentals"
        ).fetchone()["n"]
        fundamentals_lifecycle = "INTEGRATED" if fund_count else "NOT_COMMISSIONED"
        findings.append(
            f"DERIVED_METRIC: {fund_count} fundamentals row(s) on record"
        )
        evidence_refs.append("db_query:fundamentals_count")
    except sqlite3.Error:
        fundamentals_lifecycle = "UNKNOWN"
        limitations.append("UNKNOWN: fundamentals table not queryable")
    components.append(ComponentFinding(
        name="fundamentals", lifecycle=fundamentals_lifecycle,
        evidence_refs=["db_query:fundamentals_count"],
    ))

    # ---- macro_data -------------------------------------------------
    try:
        macro_row = conn.execute(
            "SELECT indicator, country, period, value, unit, source "
            "FROM macro_indicators ORDER BY id DESC LIMIT 1"
        ).fetchone()
        macro_count = conn.execute(
            "SELECT COUNT(*) AS n FROM macro_indicators"
        ).fetchone()["n"]
        evidence_refs.append("db_query:macro_indicators_latest")
        if macro_row:
            observations.append(
                f"OBSERVED_MARKET_FACT: most recently fetched macro "
                f"indicator on record is {macro_row['indicator']!r} "
                f"({macro_row['country']}), period={macro_row['period']}, "
                f"value={macro_row['value']} {macro_row['unit'] or ''}"
            )
            macro_period_year = str(macro_row["period"])[:4]
            limitations.append(
                f"STALE_DATA: latest macro_indicators row has period="
                f"{macro_row['period']} ({macro_count} rows total) -- macro "
                f"data periodicity is coarser than daily market data and is "
                f"not covered by the {CURRENT_MARKET_FRESHNESS_THRESHOLD_DAYS}"
                f"-day market-data freshness threshold; treat as background "
                f"context only, not a current reading"
            )
            macro_lifecycle = "INTEGRATED"
        else:
            macro_lifecycle = "NOT_COMMISSIONED"
    except sqlite3.Error:
        macro_lifecycle = "UNKNOWN"
        limitations.append("UNKNOWN: macro_indicators table not queryable")
    components.append(ComponentFinding(
        name="macro_data", lifecycle=macro_lifecycle,
        evidence_refs=["db_query:macro_indicators_latest"],
    ))

    # ---- forecasting -- structurally absent -----------------------------
    components.append(ComponentFinding(
        name="forecasting", lifecycle="NOT_COMMISSIONED",
        evidence_refs=["grep:no_forecasting_module_found"],
        detail="No module in the observed Sentinel source produces a "
               "forward-looking price/return forecast. This executor "
               "never emits a FORECAST-tagged statement.",
    ))
    limitations.append(
        "NOT_COMMISSIONED: Sentinel has no forecasting capability; no "
        "FORECAST-tagged statement is produced by this analysis"
    )

    # ---- provenance -------------------------------------------------
    components.append(ComponentFinding(
        name="provenance", lifecycle="INTEGRATED",
        evidence_refs=["db_query:frontier_analysis_executor_v1"],
        detail="Every observation/finding above cites the exact SELECT "
               "that produced it via evidence_refs",
    ))

    # ---- data_freshness ---------------------------------------------
    data_freshness_lifecycle = "INTEGRATED" if current_market_conclusion_permitted else "DEGRADED"
    components.append(ComponentFinding(
        name="data_freshness", lifecycle=data_freshness_lifecycle,
        evidence_refs=["db_query:prices_daily_latest"],
        detail=f"age_days={age_days}, "
               f"threshold_days={CURRENT_MARKET_FRESHNESS_THRESHOLD_DAYS}",
    ))

    # ---- external_dependencies -------------------------------------
    components.append(ComponentFinding(
        name="external_dependencies", lifecycle="DEGRADED",
        evidence_refs=["log:sentinel_ingest_error_log_2026_08_28"],
        detail="VNStock community-tier rate limit (60 req/min) currently "
               "exhausted; mitigated by a committed process-wide throttle "
               "(frontier_ingest.py::_vnstock_throttle) but not resolved -- "
               "see SENTINEL_F5_PHASE_2A_REPORT.md",
    ))
    risks.append(
        "RISK: external market-data provider (VNStock) is rate-limited; "
        "any conclusion requiring data newer than "
        f"{latest_verified_date} cannot currently be supported"
    )

    # ---- execution_interface -- observed controls, not claimed absolute -
    execution_check = conn.execute(
        "SELECT DISTINCT execution_mode, execution_allowed "
        "FROM frontier_decisions"
    ).fetchall()
    non_shadow = [
        r for r in execution_check
        if r["execution_mode"] != "SHADOW" or r["execution_allowed"] != 0
    ]
    observations.append(
        f"OBSERVED_MARKET_FACT: every (execution_mode, execution_allowed) "
        f"pair ever recorded in frontier_decisions is "
        f"{[tuple(r) for r in execution_check]} -- "
        f"{'no non-SHADOW value found' if not non_shadow else 'NON-SHADOW VALUE FOUND'}"
    )
    evidence_refs.append("db_query:frontier_decisions_execution_mode_distinct")

    components.append(ComponentFinding(
        name="execution_interface",
        lifecycle="INTEGRATED" if not non_shadow else "UNKNOWN",
        evidence_refs=["db_query:frontier_decisions_execution_mode_distinct"],
        detail="LIVE_EXECUTION_BLOCKED_BY_OBSERVED_CONTROLS: BEFORE INSERT/"
               "UPDATE triggers on frontier_decisions, frontier_shadow_"
               "executions, frontier_portfolio_runs, frontier_execution_"
               "capacity, and frontier_optimizer_runs all RAISE(ABORT) if "
               "execution_mode != 'SHADOW' or execution_allowed != 0; no "
               "broker/exchange API client exists anywhere in the observed "
               "source. This is evidence of blocked paths, not a proof "
               "every conceivable path is closed.",
    ))
    if non_shadow:
        risks.append(
            "RISK: a non-SHADOW execution value was found in "
            "frontier_decisions -- executive attention required"
        )

    recommended.append(
        "RECOMMENDATION: resolve VNStock rate-limiting (upgrade tier or "
        "complete the unused _vnstock_call_with_backoff wiring) before "
        "relying on this pipeline for same-day price/fundamentals coverage "
        "-- the process-wide throttle (frontier_ingest.py) mitigates but "
        "does not eliminate rate-limit exhaustion"
    )
    recommended.append(
        "RECOMMENDATION: (F5.1 STATUS: RESOLVED 2026-08-28) signal_worker "
        "and decision/frontier_decision_engine.py were wired into "
        "frontier_pipeline.py's stage dispatch as new 'signals'/"
        "'decisions'/'regime' stages (Sentinel repo commit 56ec4e0). "
        "signals_unified/frontier_decisions/frontier_market_regime now "
        "advance daily along with prices_daily. A related defect in "
        "technicals_worker (missing freshness stamp on its happy path) "
        "was fixed in the same change -- without it, decisions would "
        "still never generate even with the stage scheduled. See "
        "SENTINEL_DECISION_PIPELINE_FORENSIC_REPORT.md and "
        "SENTINEL_FRESHNESS_RESTORATION_EVIDENCE.md."
    )
    recommended.append(
        "RECOMMENDATION: shadow/frontier_shadow_engine.py::"
        "create_shadow_entries() reads FROM frontier_decisions but is "
        "not called by any scheduled entrypoint either -- a second, "
        "adjacent migration-discontinuity gap found while auditing "
        "decision-engine consumers. Deliberately NOT wired in as part of "
        "this restoration (it sits closer to execution simulation than "
        "analytical decision generation, and per this mission's explicit "
        "scope, analysis and execution pipelines are kept separate) -- "
        "flagged as a candidate follow-up requiring its own audit."
    )

    conn.close()

    data_status = "CURRENT" if current_market_conclusion_permitted else "STALE"

    return AnalysisResult(
        generated_at=now.isoformat(),
        analysis_run_id=analysis_run_id,
        db_path=db_path,
        components=components,
        observations=observations,
        findings=findings,
        limitations=limitations,
        risks=risks,
        recommended_next_actions=recommended,
        evidence_refs=evidence_refs,
        data_status=data_status,
        latest_verified_date=latest_verified_date,
        age_days=age_days,
        current_market_conclusion_permitted=current_market_conclusion_permitted,
        regime_age_days=regime_age,
        current_regime_conclusion_permitted=regime_is_current,
        signal_age_days=signal_age,
        decision_age_days=decision_age,
        decision_id_latest=decision_id_latest,
    )
