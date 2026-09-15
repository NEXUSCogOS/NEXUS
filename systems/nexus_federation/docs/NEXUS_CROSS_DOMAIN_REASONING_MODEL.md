# NEXUS CROSS-DOMAIN REASONING MODEL
**NEXUS Federation F6 — 2026-08-28**

## What this document covers

How NEXUS goes from one specialist institution's finding to a
decomposed, multi-institution research program — the F6 hypothesis
(mission section 1). Implemented in
`relevance/cross_domain_router.py` and `synthesis/cross_domain_synthesis.py`.

## The reasoning chain

```
1. A specialist (DAT.AI) produces a real, evidence-backed
   InstitutionalReport, ingested through the existing generic kernel path.

2. NEXUS constructs a CrossDomainTrigger from that report -- NOT from
   the report's institution-level operating_state, but from its
   findings/cross_system_implications text, via a fixed keyword table
   (_derive_candidate_implications). candidate_implications are
   explicitly HYPOTHESES for routing, never asserted as facts.

3. assess_cross_domain_relevance() evaluates the trigger against EVERY
   known target institution independently, each via a named function
   (_assess_librarian, _assess_sentinel) that checks explicit,
   inspectable conditions -- never "because it exists."

4. For each institution found relevant, build_mission_l_librarian() /
   build_mission_s_sentinel() construct a DISTINCT DelegationProposal:
   different objective, different authority ceiling (RESEARCH vs.
   ANALYSE), different constraints -- decomposition, not duplication.

5. Each specialist executes independently (no shared in-memory state,
   separate OS processes, mission section 6) and returns through the
   SAME generic ingress every institution already uses.

6. synthesize() combines both reports into one ExecutiveSynthesis object
   -- never a concatenation -- preserving each institution's own claim
   vocabulary verbatim while computing one coarse
   executive_conclusion_class from a fixed decision table.
```

## What NEXUS does NOT do

- Does not infer relevance from an opaque/learned score.
- Does not fabricate a specialist's contribution if that specialist is
  unavailable (see F6_FAILURE_MODEL.md).
- Does not force a positive conclusion when the evidence doesn't support
  one (see EXECUTIVE_RECOMMENDATION_POLICY.md).
- Does not grant any institution authority beyond ANALYSE/RESEARCH for a
  cross-domain investigation.

## Known limitations (see F6_SCIENTIFIC_EVALUATION.md for the full account)

- `candidate_implications` derivation is a fixed keyword table against
  DAT.AI's report text -- a semantically equivalent finding phrased
  differently could fail to route. Deterministic and inspectable, but
  not semantic understanding.
- Only two target institutions are known (`KNOWN_TARGET_INSTITUTIONS =
  ("librarian", "sentinel")`) -- adding a third requires a new, explicit
  `_assess_<institution>` function, not a generic fallback.
