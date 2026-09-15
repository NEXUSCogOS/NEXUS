# NEXUS Executive State Model

**Status**: GROUNDED. `state/executive_state.py::ExecutiveStateClass`.

## The seven classes

`OBSERVED`, `DERIVED`, `INFERRED`, `PREDICTED`, `UNKNOWN`, `STALE`, `CONTRADICTORY`.

## The declared ceiling for F1

**`MAX_REACHABLE_CLASS_THIS_PHASE = DERIVED`.**

NEXUS Federation F1 never independently re-verifies an institution's own
infrastructure — it has no live database credentials into DAT.AI's
PostGIS, no direct filesystem access to re-run DAT.AI's own checks. Every
accepted, evidence-resolved capability status is therefore `DERIVED`
(computed from the institution's own accepted, evidenced report), never
`OBSERVED` (which would require NEXUS's own independent re-verification —
correctly deferred, not silently claimed). This ceiling is a module-level
constant, not just a convention, so a future edit that tried to assign
`OBSERVED` without building the actual independent-verification mechanism
first would be a visible, deliberate change to this file, not an accident.

## How the other five classes are actually reached (not aspirational)

- **`UNKNOWN`**: a capability's `evidence_refs` failed to resolve
  (`evidence/resolver.py`). Proven: `tests/failure/test_failure_modes.py`#4.
- **`STALE`**: the accepted report's `temporal_classification` is `STALE`
  or `EXPIRED` (see `TEMPORAL_STATE_MODEL.md`) — every capability in that
  report is marked `STALE`, not silently treated as current. Proven:
  `tests/temporal/test_kernel_ordering.py::test_stale_report_accepted_but_visibly_flagged`.
- **`CONTRADICTORY`**: a capability's `reported_lifecycle` regressed on
  the maturity ladder from what was previously accepted, with no
  `findings`/`limitations` text mentioning that capability by name to
  explain the regression. Proven: `tests/state/test_contradiction_detection.py`.
- **`INFERRED`** and **`PREDICTED`**: not reached by any code path in F1.
  Reserved for future work where NEXUS combines evidence across multiple
  institutions to draw a conclusion no single report states directly
  (`INFERRED`) or projects a future state (`PREDICTED`) — neither exists
  yet, honestly, because only one institution (DAT.AI) is federated.

## Why this matters

Distinguishing *what* an institution claims from *how well NEXUS knows it*
is the actual epistemic contribution of this executive-state layer — it is
what makes "DAT.AI says zoning_api is INTEGRATED" and "NEXUS has
independently confirmed zoning_api is INTEGRATED" two different, never-
conflated statements. F1 only ever makes the first kind of statement.
