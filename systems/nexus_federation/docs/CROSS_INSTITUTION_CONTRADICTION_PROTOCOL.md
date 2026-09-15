# CROSS-INSTITUTION CONTRADICTION PROTOCOL
**NEXUS Federation F6 — 2026-08-28**

## Rule

Neither institution's finding is ever suppressed, softened, or omitted
to make the executive conclusion look more coherent. Both institutions'
finding text is always present verbatim in
`ExecutiveSynthesis.supporting_findings` /
`.contradictory_findings` / `.uncertainties`, tagged by institution
(`[LIBRARIAN] ...` / `[SENTINEL] ...`).

## Detection

Each finding is bucketed independently (`_bucket()`, matching only the
finding's leading epistemic tag — see NEXUS_EXECUTIVE_SYNTHESIS_MODEL.md
for why anywhere-in-text matching was rejected). If Librarian produces a
SUPPORT-bucketed finding and Sentinel produces a CONTRADICT-bucketed
finding (or vice versa) for the same trigger, `executive_conclusion_class
= CONTRADICTORY_EVIDENCE`.

## Proof (fixtures only, mission section 22's explicit instruction)

`test_f6_contradiction_preserved_with_fixtures` constructs two
controlled fixture reports:

- Librarian: `CONSENSUS: policy context suggests potential material economic impact`
- Sentinel: `CONTRADICTORY: available financial data shows no supported market/company implication`

Result: `CONTRADICTORY_EVIDENCE`, with both original sentences verified
present verbatim in the synthesis output. This fixture is NOT evidence
of any real-world F6 conclusion — it proves only that the mechanism
itself preserves contradiction rather than collapsing it.

## Independent corroboration vs. contradiction

The inverse case — both institutions SUPPORT-bucketed — is recorded as
`INDEPENDENT_CROSS_DOMAIN_CORROBORATION` ONLY if their evidence_refs sets
are disjoint (mission section 14's explicit anti-double-counting rule).
If they share even one evidence_ref, the corroboration is NOT recorded,
because it would be the same originating fact counted twice, not two
independent confirmations.

## What NEXUS does when both institutions are simply uncertain

Distinct from contradiction: if BOTH institutions report
`INSUFFICIENT`-bucketed findings (neither supporting nor contradicting),
`executive_conclusion_class = INSUFFICIENT_EVIDENCE` — a real, observed
outcome in this mission's Section 21 (partial-synthesis) test, and the
outcome an earlier, since-fixed bucketing defect incorrectly produced
for the FULL (non-partial) real run too (see F6_SCIENTIFIC_EVALUATION.md
for the full account of that defect and its fix).
