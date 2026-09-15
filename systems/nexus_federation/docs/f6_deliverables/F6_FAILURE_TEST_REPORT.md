# F6 FAILURE TEST REPORT
**NEXUS Federation F6 — 2026-08-28**

## Section 21: Specialist Failure (One Recipient Unavailable)

**Test:** `test_f6_specialist_failure_partial_synthesis`

Simulated: Sentinel unavailable (Process C never invoked). NEXUS:

- Retained Librarian's real result (ingested, accepted)
- Marked `missing_institutions: ["sentinel"]` explicitly
- Did NOT fabricate a Sentinel contribution
- Produced `executive_conclusion_class = INSUFFICIENT_EVIDENCE` with `partial: true`
- No whole-federation failure: NEXUS process completed normally, exit code 0

**Result: PASS**

## Section 22: Contradictory Results (Fixtures Only)

**Test:** `test_f6_contradiction_preserved_with_fixtures`

Per the mission's explicit instruction, this test uses controlled fixture
reports ONLY — not real F6 evidence — to prove the synthesis logic itself
preserves contradiction rather than suppressing one institution:

- Fixture Librarian report: `CONSENSUS: policy context suggests potential material economic impact`
- Fixture Sentinel report: `CONTRADICTORY: available financial data shows no supported market/company implication`
- Result: `executive_conclusion_class = CONTRADICTORY_EVIDENCE`
- Both institutions' original finding text verified present verbatim in
  the synthesis output (`supporting_findings` / `contradictory_findings`)

**This fixture result is NOT evidence of any real-world F6 conclusion.**
It proves the synthesis logic's structural behavior only.

**Result: PASS**

## Section 23: Duplicate / Restart

**Test 1:** `test_f6_duplicate_trigger_replay_no_duplicate_missions`

Replayed Process A against the identical, already-accepted DAT.AI
report. Found and fixed a real gap during construction: `trigger_id` was
originally a random `uuid4()` per invocation (meaning every replay
created a fresh, distinct trigger and thus fresh, distinct delegations —
true duplicates). Fixed by making `trigger_id` and each delegation's
`proposal_id` deterministic (`uuid5`, derived from
`source_report_id + source_finding_id` / `trigger_id + recipient`).
Also discovered `persistence.db.FederationStore.record_delegation_
proposal`'s own idempotency notion (`f"{mission_id}:{delegation_id}"`)
is a DIFFERENT, narrower mechanism than `delegation/idempotency.py`'s
richer `compute_idempotency_key` — the duplicate check had to target the
former, or it silently never matched. After the fix: replay correctly
reports `already_existed: true` for both delegations, `count_delegations()`
unchanged (2 → 2).

**Test 2:** `test_f6_process_d_restart_no_duplicate_synthesis`

Ran Process D twice against the identical pair of (Librarian, Sentinel)
report IDs. `state_event_log` (the executive semantic state) stayed at 1
row both times; `report_log` (receipt/ingestion-attempt log) correctly
grew (4 → 6), matching the same receipt-vs-state-transition distinction
already proven for F5.1. Each Process D invocation computes its own
in-memory `ExecutiveSynthesis` object (with a fresh `synthesis_id`) —
that computation itself is cheap and not deduplicated — but only the
FIRST is ever persisted as an executive state event, keyed by a
deterministic identity derived from the sorted input report_ids.

**Result: PASS (both)**

## Section 28: Negative Control

**Test:** `test_f6_negative_control_no_material_effect`

Used the OTHER real, DAT.AI-ingested zone (project_id `c4`, a routine
subdivision plan for already-built-up Bien Hoa city, not adjacent to
major new infrastructure), with `candidate_implications: []` (NEXUS's
own trigger-construction step proposed no routing hypothesis). Result:

- `librarian_relevance.relevant = false`
- `sentinel_relevance.relevant = false`
- Zero delegations created

NEXUS did not manufacture relevance merely because both institutions
exist and are reachable.

**Result: PASS**

## Summary Table

| Test | Section | Result |
|---|---|---|
| Specialist failure (partial synthesis) | 21 | PASS |
| Contradiction preserved (fixtures) | 22 | PASS |
| Duplicate trigger replay | 23 | PASS |
| Process D restart | 23 | PASS |
| Negative control | 28 | PASS |
