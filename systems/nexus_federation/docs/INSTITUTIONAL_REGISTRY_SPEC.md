# Institutional Registry Spec

**Status**: GROUNDED. `registry/models.py::InstitutionRegistryEntry`, persisted in `persistence/db.py`'s `institution_registry` table.

## Fields (as implemented)

`institution_id`, `institution_type`, `canonical_path`, `contract_version`,
`authority_class` (defaults `A1_OBSERVATION` — DAT.AI has made no A3+
claim), `maturity` (verbatim `operating_state` from the last accepted
report), `last_report_timestamp`, `last_verified_cycle`, `component_states`
(list of `ComponentState`, see `CAPABILITY_EVIDENCE_MODEL.md`),
`dependencies`, `external_dependencies`, `capabilities`, `evidence_refs`,
`storage_dependencies`, `registered_at`.

## The one hard rule

**State must derive from accepted evidence. Never manually assert
"healthy."** Every field above is either a constant fixed at first
registration (`institution_id`, `canonical_path`, `registered_at`) or
overwritten only by `kernel.py::FederationKernel.ingest_report()` after a
report has passed schema validation AND temporal-ordering validation.
There is no code path anywhere in this module that sets `maturity` or
`component_states` to a value not read directly off an accepted
`InstitutionalReport`.

## Verified state (as of this mission's own test runs)

DAT.AI's registry entry, ingested from a real report against a live
disposable PostGIS instance:

```
institution_id: dat_ai
maturity: INTEGRATED
component_states:
  zoning_api: reported_lifecycle=INTEGRATED, executive_state_class=DERIVED, evidence_resolved=True
  valuation: reported_lifecycle=NOT_COMMISSIONED, executive_state_class=DERIVED, evidence_resolved=True
```

## What is NOT yet in the registry

`dependencies`/`external_dependencies`/`storage_dependencies` are present
as fields but not currently populated by `kernel.py` from any DAT.AI
report field (DAT.AI's contract does not carry a structured
dependency-graph field yet). Left as empty lists — an honest gap, not
fabricated content — see `FEDERATION_F2_ENTRY_CRITERIA.md`.
