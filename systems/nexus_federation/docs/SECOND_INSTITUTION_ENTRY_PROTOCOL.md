# SECOND INSTITUTION ENTRY PROTOCOL
**NEXUS Federation F2 — 2026-08-27**

## CURRENT VERIFIED IMPLEMENTATION

### The dispatch mechanism is now generic

F1's ingress hardcoded `from institutional.contract import
InstitutionalReport, validate_report` — a direct, permanent coupling to
DAT.AI's module. NEXUS Federation F2 replaces this with
`ingress/contract_registry.py`: a registry mapping
`institution_id -> (validate_fn, known_schema_versions)`. DAT.AI remains
registered exactly as before (`"dat_ai" ->
institutional.contract.validate_report`); `ingress/validator.py`'s logic
now looks up the incoming payload's `institution` field in this registry
BEFORE attempting any validation, rejecting fail-closed
("no registered contract for institution ...") if nothing is registered.

**Adding a second real institution is a registry entry, not a code
change to `ingress/validator.py`, `kernel.py`, or any state/evidence/
relevance module.**

### Proven: zero production-code changes needed

`tests/contract/test_second_institution_generic.py` registers a wholly
synthetic `test_fixture_institution` (`tests/contract/synthetic_fixture.py`
— explicitly NOT a claimed real institution, never imported by production
code) with:
- a different `schema_version` string (`"0.1.0-test-fixture"`, not DAT.AI's `"1.1.0"`)
- a different `operating_state` vocabulary (`RESEARCH_ACTIVE`, which DAT.AI has never emitted)
- different capability names (`literature_review`, `corpus_health`)
- a different capability-lifecycle vocabulary (`DRAFT, PEER_REVIEWED, PUBLISHED, RETRACTED`)
- no `confidence` field on its capability status at all

...and proves this second institution:
- is correctly REJECTED before registration (fail-closed, not silently accepted)
- is correctly ACCEPTED after registration, with zero changes to any production module
- receives its own independent registry entry, coexisting with DAT.AI's
- has fully independent temporal ordering (an out-of-order report for the
  fixture institution never touches DAT.AI's accepted state)

### The one real, disclosed constraint this surfaced

`capability_statuses[].lifecycle` must be exposed as something with
`.value` (i.e. a `str` Enum, or equivalent) — `kernel.py` calls
`cap.lifecycle.value` when building `ComponentState`/state events. This
is now an explicit, documented cross-institution contract requirement
(the synthetic fixture satisfies it via its own `FixtureCapabilityLifecycle`
enum), not a silent assumption. `state.capability.lifecycle_rank()` already
degrades gracefully (returns `None`, contradiction-detection simply
doesn't apply) for any lifecycle string outside DAT.AI's specific ladder
— proven by the fixture using an entirely different vocabulary.

## REQUIRED INTERFACE FOR A NEW INSTITUTION

1. A validate function accepting `dict -> <report object>`, raising on
   any malformed input (fail-closed), returning an object exposing at
   minimum: `institution` (str), `mission_id`, `cycle_id`, `timestamp`
   (ISO 8601, timezone-aware), `operating_state` (anything with `.value`),
   `capability_statuses` (list of objects with `.name`, `.lifecycle`
   [must expose `.value`], `.evidence_refs`, `.detail`), `objective`,
   `findings`, `limitations`, `evidence_refs`, `schema_version`,
   `.model_dump(mode="json")`.
2. A call to `ingress.contract_registry.register_contract(institution_id,
   validate_fn, known_schema_versions)`.
3. Evidence refs the institution cites must be resolvable under a search
   root NEXUS knows about (`evidence/resolver.py: SEARCH_ROOTS`) — a new
   root is a one-line addition, not a logic change.

## TARGET

This directly informs Librarian's own entry requirements — see
`LIBRARIAN_F3_ENTRY_CRITERIA.md`, which specifies exactly this interface
applied to what Librarian would need to expose.

## LIMITATIONS

- This proves GENERALITY of the dispatch/kernel mechanism. It does not
  and cannot prove that any SPECIFIC real second institution (Librarian
  or otherwise) is ready — that requires that institution's own donor
  recovery / commissioning work, which is out of scope here (the mission
  explicitly: "Do not recover Librarian yet").
- The registry itself (`ingress/contract_registry.py`) is in-process,
  module-level global state — fine for a single-process federation kernel,
  but would need to become configuration-driven or externally persisted
  before multiple federation processes could share a consistent view of
  which institutions are registered.
