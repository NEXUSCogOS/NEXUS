# F6 SCIENTIFIC EVALUATION
**NEXUS Federation F6 — 2026-08-28**

Per mission section 27: evaluated on named criteria, no arbitrary overall
"cognition score."

## Trigger validity
**PASS.** The triggering finding is real: DAT.AI's own, unmodified
`worker/tasks/ingest_zoning_data.py` was run against a genuine Vietnamese
government planning-portal export (`quyhoach.xaydung.gov.vn`), producing
a real `PlanningZone` row for Cẩm Đường commune, Long Thành district,
Đồng Nai — the commune area adjacent to Long Thanh International
Airport. Geometric proximity (~1.2km boundary distance) was computed
directly from the ingested WKT geometry via `shapely`, not asserted.
See F6_TRIGGER_EVIDENCE.json and the "regeneration_ddl" note in
`process_dat_ai_trigger_source.py` for full reproducibility.

## Routing correctness
**PASS, with one honest caveat.** Both institutions were routed to for
stated, inspectable reasons (`F6_ROUTING_DECISION.json`), not because
they merely exist — verified negatively by the Section 28 test (same
mechanism correctly declined to route for the C4 zone). Caveat:
`candidate_implications` are derived from a fixed keyword table matched
against DAT.AI's own report text (`_derive_candidate_implications`) —
this is deterministic and inspectable, but it is a keyword heuristic, not
a semantic understanding of the finding. A differently-worded but
equivalent DAT.AI finding could fail to route if it didn't happen to use
matching keywords. This limitation is structurally identical to
Librarian's own disclosed keyword-marker retrieval heuristic.

## Delegation specificity
**PASS.** Mission L and Mission S have distinct objectives, distinct
`delegation_id`/`mission_id`, distinct authority ceilings (RESEARCH vs.
ANALYSE), and distinct constraint lists — not templated boilerplate.
Verified structurally via `test_f6_full_four_process_e2e`.

## Source authenticity
**PASS.** DAT.AI: real government-sourced planning data. Librarian: real
retrieval against its real 22-source corpus (`arxiv:1908.03438`,
`arxiv:2107.10894`, `arxiv:2602.12430`, `arxiv:2004.01504` — genuine
academic identifiers, not fabricated). Sentinel: real `companies`/
`prices_daily`/`frontier_decisions` rows from the actual, F5.1-restored
production database.

## Evidence completeness
**PARTIAL, honestly reported as such.** Librarian's corpus (22
AI/technical preprints) has no source addressing Vietnamese
infrastructure economics — correctly resulting in
`INSUFFICIENT_EVIDENCE`, not a fabricated finding. Sentinel's
`companies` table discloses sector only, never facility-level geography
— every entity mapping tested tops out at INDIRECT or HYPOTHETICAL, none
reach DIRECT. This is a genuine evidence gap in the underlying
institutions, not a synthesis defect, and is exactly the kind of honest
non-result the mission's section 1 explicitly asked F6 not to
pre-declare away.

## Provenance completeness
**PASS.** Both chains (DAT.AI → NEXUS → Librarian → NEXUS; DAT.AI →
NEXUS → Sentinel → NEXUS) resolve to persistent identifiers at every hop
— see F6_PROVENANCE_GRAPH.json, captured from one real execution.

## Claim-class preservation
**PASS.** Librarian's `INSUFFICIENT_EVIDENCE`/`SOURCE_FACT` tags and
Sentinel's `DERIVED_METRIC`/`MODEL_ESTIMATE`/`OBSERVED_MARKET_FACT` tags
are carried through into `supporting_findings`/`contradictory_findings`/
`uncertainties` VERBATIM — the synthesis's coarse SUPPORT/CONTRADICT/
INSUFFICIENT bucketing (used only to pick `executive_conclusion_class`)
never overwrites or discards the original text.

**Defect found and fixed during this evaluation, not merely disclosed:**
the first version of the bucketing heuristic (`_bucket()` in
`synthesis/cross_domain_synthesis.py`) matched marker substrings anywhere
in a finding's text. This caused a real miscalculation: a Sentinel
entity-mapping finding whose leading (and only real) tag was
`DERIVED_METRIC` also happened to contain the word "classified UNKNOWN"
later in the same sentence (describing the LHG ticker's mapping outcome,
not an epistemic claim about the finding itself) — the substring match
picked that up and bucketed the ENTIRE finding as `INSUFFICIENT`, which
then drove `executive_conclusion_class` to `INSUFFICIENT_EVIDENCE` for a
reason unrelated to Sentinel's actual epistemic position. Fixed by
matching only the LEADING tag (text before the first colon) — the
convention every finding in this mission actually follows. Re-running
the full pipeline after the fix changed the real result from
`INSUFFICIENT_EVIDENCE` to `PARTIALLY_SUPPORTED` (Librarian's one real,
if tangential, `SOURCE_FACT` — a land-use-mapping methodology paper —
now correctly registers as support; Sentinel's `DERIVED_METRIC`/
`MODEL_ESTIMATE` findings correctly register as `NEUTRAL`, not
`INSUFFICIENT`, since Sentinel never actually emitted an
`INSUFFICIENT_EVIDENCE`/`UNKNOWN`-tagged finding). This is the version
reflected in F6_EXECUTIVE_SYNTHESIS.json and everywhere else in this
mission's deliverables.

## Contradiction handling
**PASS** (fixture-verified, section 22). The real F6 run produced
`PARTIALLY_SUPPORTED` (one tangential Librarian support, no
contradiction) — the `CONTRADICTORY_EVIDENCE` path itself is proven
correct via controlled fixtures, honestly labeled as such, not claimed
as a real F6 result.

## Temporal alignment
**PASS.** `temporal_mismatches` correctly flagged the DAT.AI observation
as 318 days old (relative to synthesis time) and Sentinel's macro
context as stale relative to its own current price/decision data — both
usable as historical context, neither silently presented as current.

## Synthesis traceability
**PASS.** `confidence_basis` states the exact rule inputs (support count,
contradiction count, corroboration count, partial flag) with zero
learned/opaque scoring.

## Unsupported claim count
**0**, per this run's synthesis output. Every `finding`/`observation` in
both institutional reports carries at least one `evidence_ref` (enforced
structurally by the generic contract's `_findings_require_evidence`
validator) that resolves to a real, checkable source (arxiv ID, DB row,
or WKT geometry computation).

## Reproducibility
**PASS**, with one caveat documented in `F6_REPRODUCIBILITY_PROTOCOL.md`:
the DAT.AI zoning ingestion step requires `geoalchemy2`/`shapely` in a
dedicated venv (unavailable in the default sandboxed environment used
for regression), so the F6 test suite seeds its trigger from a
pre-ingested SQLite artifact rather than re-running DAT.AI's PostGIS
pipeline live each time. The regeneration command is documented verbatim
in `process_dat_ai_trigger_source.py`'s own docstring.

## Summary

| Criterion | Verdict |
|---|---|
| Trigger validity | PASS |
| Routing correctness | PASS (keyword-heuristic caveat) |
| Delegation specificity | PASS |
| Source authenticity | PASS |
| Evidence completeness | PARTIAL (honestly reported) |
| Provenance completeness | PASS |
| Claim-class preservation | PASS (bucketing fragility disclosed) |
| Contradiction handling | PASS (fixture-verified) |
| Temporal alignment | PASS |
| Synthesis traceability | PASS |
| Unsupported claim count | 0 |
| Reproducibility | PASS (venv caveat documented) |

No single "cognition score" is assigned, per mission section 27's
explicit instruction.
