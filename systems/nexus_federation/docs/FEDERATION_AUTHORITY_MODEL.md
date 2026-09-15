# FEDERATION AUTHORITY MODEL
**NEXUS Federation F2 — 2026-08-27**

## CURRENT VERIFIED IMPLEMENTATION

`authority/model.py: AuthorityLevel` — a closed, ordered taxonomy:

```
OBSERVE < RESEARCH < ANALYSE < GENERATE_INTERNAL < MODIFY_REVERSIBLE
< ARCHITECTURAL_CHANGE < EXTERNAL_ACTION < HIGH_CONSEQUENCE_ACTION
```

`MAX_GRANTABLE_AUTHORITY_THIS_PHASE = ANALYSE`. `exceeds_phase_ceiling()`
is a pure rank comparison. `delegation/schema.py: DelegationProposal`
carries `authority: AuthorityLevel` (default `ANALYSE`) and a
`model_validator` that REFUSES construction if `authority` exceeds the
phase ceiling — this is a structural block, the same pattern used
elsewhere in this estate (e.g. DAT.AI's own block on self-promotion to
`OPERATIONAL`), not a convention a future call site could quietly ignore.

### Proven (`tests/unit/test_authority_model.py`)

- Every level at or below `ANALYSE` constructs successfully.
- Every level above `ANALYSE` (`GENERATE_INTERNAL` through
  `HIGH_CONSEQUENCE_ACTION`) raises `pydantic.ValidationError` at
  construction time — parametrized over all five, not one hand-picked
  case.
- `relevance/router.py`'s only delegation-producing path defaults to
  `ANALYSE` and is never given a way to request anything higher.
- `test_a_recipient_cannot_infer_broader_authority_from_objective_text`:
  a deliberately dramatic-sounding `objective` string ("take over the
  financial system and execute all trades immediately") does not change
  the granted `authority` field — the field is the ONLY place authority is
  expressed, exactly as the mission requires.

## TARGET

- As real recipient institutions (Sentinel, Librarian, etc.) come online,
  each delegation's `authority` should be checked AGAIN on the recipient
  side before acting — this document only covers what NEXUS Federation
  grants when ISSUING a delegation, not enforcement at the receiving end
  (which does not exist yet, since no recipient is connected).
- A per-recipient-institution authority ceiling (some institutions may
  legitimately need more than ANALYSE eventually; that is a future,
  deliberate, reviewed change to this file's ceiling constant, one
  institution at a time — never inferred).

## LIMITATIONS

- The ceiling (`MAX_GRANTABLE_AUTHORITY_THIS_PHASE`) is a single global
  constant, not yet parametrized per recipient or per capability. Every
  delegation this federation can currently issue is ANALYSE regardless of
  which institution or category triggered it — appropriate for F1/F2
  (exactly one delegation-producing rule exists), but will need
  generalizing before a second rule with different authority needs
  exists.
