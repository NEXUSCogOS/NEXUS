# EXECUTIVE RECOMMENDATION POLICY
**NEXUS Federation F6 — 2026-08-28**

## Allowed recommended actions (mission section 25)

`synthesize()` selects from a small, fixed set:

- "request more research" / "request DAT.AI re-analysis with facility-level geographic disclosure"
- "request fresher data"
- "continue monitoring"
- "create hypothesis" / "create bounded experiment" (not yet triggered by any real F6 run's rules — no code path selects these today, listed here as an allowed future value only)
- "retry delegation to {missing institution}" (partial-synthesis case)

**Never included:** any instruction to execute a financial transaction,
place an order, or otherwise convert a cross-domain conclusion directly
into a trade. This is enforced structurally, not by convention: no
function in `synthesis/cross_domain_synthesis.py` or anywhere in the F6
subprocess helpers imports, calls, or references any order/broker
interface — none exists anywhere in the observed Sentinel codebase (see
SENTINEL_DECISION_ENGINE_AUDIT.md).

## The prohibited_actions list

Every `ExecutiveSynthesis` carries an identical, hardcoded
`prohibited_actions` list, regardless of conclusion:

```
PROHIBITED: place a live order
PROHIBITED: cancel an order
PROHIBITED: change execution_mode
PROHIBITED: change execution_allowed
PROHIBITED: invoke broker execution
PROHIBITED: publish externally
PROHIBITED: modify another institution's data or code
PROHIBITED: convert this conclusion directly into a financial trade
```

This list does not vary with `executive_conclusion_class` — even a
`SUPPORTED_CROSS_DOMAIN_INFERENCE` carries the identical prohibition set.
No conclusion, however strong, unlocks a broader action space.

## Authority ceilings enforced upstream, not just declared here

Both delegations are constructed with an authority level that
structurally cannot exceed `MAX_GRANTABLE_AUTHORITY_THIS_PHASE = ANALYSE`
(`authority/model.py`, proven in F5) — Librarian's Mission L uses
`RESEARCH`, Sentinel's Mission S uses `ANALYSE`. Neither delegation
schema permits `EXTERNAL_ACTION` or `HIGH_CONSEQUENCE_ACTION`; a
delegation attempting either fails
`DelegationProposal`'s own `_authority_never_exceeds_phase_ceiling`
validator before it can even be persisted (proven directly in F5's
`test_f5_live_execution_rejected` and re-verified for F6 in
`test_f6_full_four_process_e2e`'s use of the same `AuthorityLevel`
enum).

## No profitability inference

Per mission section 10's explicit instruction, Sentinel's
`decision_engine`/`regime_detection` outputs are fresh (F5.1-restored)
but have zero historical validation (SENTINEL_DECISION_ENGINE_AUDIT.md,
SENTINEL_REGIME_ENGINE_AUDIT.md). Every Sentinel finding referencing a
decision/regime output in this mission explicitly states this in the
same sentence ("NOT a validated predictor... No profitability inference
may be drawn from it") — never presented as a signal to act on.
