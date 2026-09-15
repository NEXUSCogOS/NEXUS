# YOUTUBE FACT-CHECK PROTOCOL
**NEXUS Federation F8 — 2026-08-28**

Mission section 21: runs AFTER script generation, BEFORE final render
acceptance. Implemented in `script.py::fact_check_script()`.

## Outcome vocabulary

`SUPPORTED`, `PARTIAL`, `UNSUPPORTED`, `CONTRADICTORY`, `STALE`.

## Rule (fixed, disclosed, never an opaque score)

For each script segment carrying a `claim_id`:

1. If no matching claim-ledger entry exists (or it is `REJECTED`) ->
   `UNSUPPORTED`, `action_taken=REMOVED`.
2. Else if the claim text appears in the evidence pack's own
   `contradictions` list -> `CONTRADICTORY`, kept but flagged (never
   silently dropped -- a contradiction is itself a finding).
3. Else if the claim_id/claim_text appears in `stale_evidence` ->
   `STALE`, kept but flagged.
4. Else if the ledger's `verification_status == VERIFIED` -> `SUPPORTED`.
5. Else if `verification_status == PARTIAL` -> `PARTIAL`.
6. Else -> `UNSUPPORTED`, `action_taken=REMOVED`.

`EDITORIAL_TRANSITION` segments (intro/outro/caveat lines) carry no
`claim_id` and are never fact-checked, because they assert no fact
(mission section 9's own separation).

## Removal, not silent pass-through

Every `UNSUPPORTED` segment is dropped from the script BEFORE it reaches
render -- `fact_check_script()` returns a `(results, revised_script)`
pair; `revised_script` is what actually gets narrated/rendered.
Confirmed directly by `test_f8_unsupported_claim_negative_control`: an
injected sensational claim with no matching evidence item is REMOVED,
and the surrounding editorial-transition segments survive unchanged.

## Anti-hallucination check (mission section 10)

`script.py::anti_hallucination_check()` runs before fact-check: every
numeric token in a FACT/ANALYSIS segment must appear somewhere in the
evidence pack's own claim text, or it is flagged as a possible
fabricated statistic. This is a real, running check against real
evidence text, not a placeholder that always passes -- but it is scoped
to numeric tokens only; name/quote/policy-claim verification is not yet
implemented (disclosed limitation, not silently skipped).

## Real run result (this mission's defining experiment)

Every real segment generated from the F6 executive synthesis (5
DERIVED_METRIC entity-mapping findings, real Vietnamese industrial-park
tickers) reached `SUPPORTED`/`PARTIAL` -- zero `UNSUPPORTED` claims
survived to render in the real run. See
YOUTUBE_PRODUCTION_E2E_EVIDENCE.md for the exact captured values.
