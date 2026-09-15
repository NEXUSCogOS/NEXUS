# Delegation Protocol

**Status**: GROUNDED. `delegation/schema.py::DelegationProposal`, produced by `relevance/router.py::assess_relevance()`.

## Scope for F1

**Proposal generation only.** No recipient institution is connected. No
proposal is ever delivered anywhere — `kernel.py` persists it to
`delegation_log` and returns it; nothing downstream consumes it. This is
deliberate, per the mission's explicit F1 boundary.

## Schema

`mission_id`, `issuer` (always `"nexus_federation"`), `recipient`,
`objective`, `reason`, `evidence_refs`, `priority` (1=highest..5=lowest,
deterministic), `authority` (always `A1_OBSERVATION` for F1 — a delegation
requests analysis, never authorizes action), `constraints`,
`resource_budget`, `ttl_deadline`, `success_criteria`, `risk_class`
(`LOW`/`MEDIUM`/`HIGH`), `parent_mission`, `requested_output_contract`
(pinned to `"InstitutionalReport v1.1.0"` — a delegate is expected to reply
in the same schema), `created_at`, `proposal_id`.

**Reproducibility**: every field traces to either the triggering
`RelevanceSignal` (itself required to carry a `materiality_basis`, no
unstated numbers) or the router's own deterministic threshold logic
(`MATERIALITY_THRESHOLD = 0.5`, `MIN_LIFECYCLE_RANK = TESTED`). Given the
same signal and the same capability lifecycle, `assess_relevance()` always
returns the identical proposal (module the timestamp/UUID) — proven by
`tests/unit/test_relevance_router.py`.

## Honest limitation: no automatic signal extraction

DAT.AI's contract carries findings as free-text strings
(e.g. `"zoning_api: INTEGRATED -- ..."`). This protocol does **not** parse
that text for materiality via keyword-matching or NLP — that would not be
a deterministic, defensible mechanism. A `RelevanceSignal` must be
constructed with an explicit, structured `materiality` value and
`materiality_basis`. In F1, no code path derives one automatically from a
routine DAT.AI report; the mechanism is proven correct via an
explicitly-labeled synthetic test signal (`tests/unit/test_relevance_router.py`,
`observability/resource_accounting.py`'s smoke run), not from any real
DAT.AI output. DAT.AI does not currently emit change-detection findings at
all (its satellite/change-detection pipeline is not recovered — Phase D
scope), so there is nothing real to extract yet.

## Verified this mission

One real delegation proposal generated end-to-end (real DAT.AI report +
synthetic-but-labeled signal), persisted to `delegation_log`, and proven
idempotent (a duplicate cycle_id does not regenerate it — `tests/restart/
test_restart_recovery.py::test_duplicate_after_restart_does_not_regenerate_delegation`).
