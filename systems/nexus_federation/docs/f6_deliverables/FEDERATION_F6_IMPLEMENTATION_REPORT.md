# FEDERATION F6 IMPLEMENTATION REPORT
**NEXUS Federation F6 — 2026-08-28**

## What was built

1. **A real, non-fabricated cross-domain trigger.** DAT.AI's own,
   unmodified `worker/tasks/ingest_zoning_data.py` was run (via a
   dedicated venv with `geoalchemy2`/`shapely`, since neither is
   available in the default sandboxed environment) against a genuine
   Vietnamese government planning-portal export
   (`quyhoach.xaydung.gov.vn`), producing a real `PlanningZone` row for
   Cẩm Đường commune, Long Thành district, Đồng Nai — geometrically
   ~1.2km from Long Thanh International Airport (computed with
   `shapely`, not asserted). This satisfies mission section 2's explicit
   requirement not to insert a purpose-built finding.

2. **`relevance/cross_domain_router.py`** (new module): deterministic,
   per-institution relevance assessment (`assess_cross_domain_relevance`)
   and mission decomposition (`build_mission_l_librarian`,
   `build_mission_s_sentinel`), plus a transparent attention-scoring
   model (`assess_attention`). Additive — the existing single-recipient
   `relevance/router.py` (F1/F3) is untouched.

3. **`synthesis/cross_domain_synthesis.py`** (new module): the
   `ExecutiveSynthesis` object and `synthesize()` function implementing
   the full structure required by mission section 12, the
   claim-class-preserving bucketing of section 13, independent
   corroboration detection (section 14), and temporal mismatch flagging
   (section 16).

4. **A four-process F6 test harness**
   (`tests/f6/_subprocess_helpers/`, `tests/f6/test_f6_cross_domain_synthesis.py`):
   7 tests, all passing, covering the full E2E pipeline, specialist
   failure, fixture-only contradiction, duplicate trigger replay,
   Process D restart idempotency, negative control, and full
   WHY/WHAT/HOW reconstruction from stored evidence alone.

5. **Real, measured resource accounting** (`_resource_accounting.py`):
   CPU time and peak RSS via `resource.getrusage`, wall-clock elapsed
   time — every unmeasured field (storage delta, API calls/cost, model
   tokens) explicitly reported as `null`, never estimated.

## Two real defects found and fixed during construction

1. **Non-deterministic `trigger_id`/`proposal_id`** meant a trigger
   replay created genuine duplicate delegations (`count_delegations()`
   growing 2→4 on replay). Fixed by deriving both via `uuid5` from
   stable inputs (source report + zone / trigger + recipient). Also
   surfaced a real, pre-existing divergence: `persistence.db.
   FederationStore.record_delegation_proposal`'s own idempotency notion
   (`mission_id:delegation_id`) is different from `delegation/
   idempotency.py`'s richer `compute_idempotency_key` — the duplicate
   check had to target the former.

2. **Anywhere-in-text marker matching** in the synthesis bucketing
   heuristic caused a Sentinel `DERIVED_METRIC` finding to be
   misclassified as `INSUFFICIENT` because the word "UNKNOWN" appeared
   incidentally inside its text (describing an entity-mapping outcome,
   not an epistemic claim). This changed the real F6 run's
   `executive_conclusion_class` from `INSUFFICIENT_EVIDENCE` to the
   correct `PARTIALLY_SUPPORTED` once fixed (leading-tag-only matching).
   Full account in F6_SCIENTIFIC_EVALUATION.md.

Both are documented in F6_FAILURE_TEST_REPORT.md /
F6_SCIENTIFIC_EVALUATION.md rather than silently corrected — per this
mission's own standard, a wrong result gets corrected the moment it's
found, not smoothed over.

## The real result

**`executive_conclusion_class = PARTIALLY_SUPPORTED`.** Librarian's
22-source academic corpus (all AI/technical preprints) has no source
addressing Vietnamese infrastructure economics — correctly returning
`INSUFFICIENT_EVIDENCE` for the core research question, with one real
but tangential `SOURCE_FACT` (a land-use-mapping methodology paper).
Sentinel's `companies` table discloses sector only, never facility-level
geography — every one of 5 candidate tickers (KBC, SZC, GVR, IDC, LHG)
tops out at `INDIRECT` or `HYPOTHETICAL`, none reach `DIRECT`. This is a
genuine, evidence-grounded non-strong-result — exactly the kind of
outcome mission section 1 asked F6 not to pre-declare away.

## Commits

- NEXUS repo: `relevance/cross_domain_router.py`, `synthesis/`,
  `tests/f6/`, `docs/` (this report + 8 model docs), all new/additive.
- DAT.AI repo: no source changes — only a new, gitignored data artifact
  (`data/f6_evidence/planning_zones_dong_nai.db`).

## Regression

See the mission's final report for exact per-environment counts. Summary:
NEXUS federation 137 passed / 1 skipped (pre-existing); Librarian 114
passed; Sentinel 372 (native) + 8 (F5.1) passed; DAT.AI 74 passed / 21
skipped (pre-existing) / 3 collection errors (environment-only,
`geoalchemy2`, zero DAT.AI source touched). No F6-caused regression
anywhere.
