# Capability Evidence Model

**Status**: GROUNDED. `state/capability.py::ComponentState`, `state/executive_state.py::ExecutiveStateClass`.

## Two layers, never conflated

1. **`reported_lifecycle`** — the institution's own claim, verbatim
   (`NOT_IMPLEMENTED`/`IMPLEMENTED`/`TESTED`/`INTEGRATED`/
   `EMPIRICALLY_VALIDATED`/`OPERATIONAL`/`NOT_COMMISSIONED`/
   `EXTERNAL_DEPENDENCY_UNAVAILABLE`). NEXUS never rewrites this value.
2. **`executive_state_class`** — NEXUS's own classification of *how it
   knows* the above (`OBSERVED`/`DERIVED`/`INFERRED`/`PREDICTED`/`UNKNOWN`/
   `STALE`/`CONTRADICTORY`). See `NEXUS_EXECUTIVE_STATE_MODEL.md`.

## Granularity is preserved, never collapsed to one boolean

DAT.AI's real, verified registry entry (this mission):

```
zoning_api:               INTEGRATED
model_registry:           TESTED
promotion_gate:           TESTED
satellite_classification: IMPLEMENTED   (confidence 0.0, untrained)
satellite_acquisition:    EXTERNAL_DEPENDENCY_UNAVAILABLE
valuation:                NOT_COMMISSIONED
```

Six independent values, not one. `institutional_state.maturity` (the
institution-level `operating_state`) is `INTEGRATED`, matching only the
core `zoning_api` capability — an untrained classifier and an uncommissioned
valuation capability do not drag it down (proven:
`tests/integration/test_kernel_ingest.py`,
`tests/integration/test_institutional_reporter.py::
test_operating_state_not_dragged_down_by_untrained_model_or_uncommissioned_valuation`
in DAT.AI's own suite).

## Never inferred

`IMPLEMENTED → OPERATIONAL` and `INTEGRATED → EMPIRICALLY_VALIDATED` are
never inferred by NEXUS. NEXUS stores exactly what DAT.AI reported.
DAT.AI's own contract already structurally prevents self-promotion to
`OPERATIONAL` (requires `external_attestation_ref`); NEXUS adds no
additional inference on top, only the `executive_state_class` layer
describing evidence quality, which is capped at `DERIVED` this phase (see
`NEXUS_EXECUTIVE_STATE_MODEL.md`).

## Evidence resolution feeds directly into this model

If any of a capability's `evidence_refs` fail to resolve
(`evidence/resolver.py`), `executive_state_class` becomes `UNKNOWN` — the
capability's `reported_lifecycle` is still recorded (DAT.AI said what it
said), but NEXUS marks its own confidence in that claim as degraded, not
silently trusted. Proven: `tests/failure/test_failure_modes.py::test_04_missing_evidence_degrades_claim_not_silently_accepted`.
