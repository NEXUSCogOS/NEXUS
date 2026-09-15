# Institutional Message Schema

**Status**: GROUNDED. NEXUS Federation F1 (2026-08-27) consumes DAT.AI's
`institutional.contract` module directly — this document describes that
schema as consumed, not a NEXUS-side reimplementation.

## The schema NEXUS ingests

`InstitutionalReport` (schema_version `1.1.0`), defined in
`systems/dat_ai/institutional/contract.py`, imported unmodified by
`systems/nexus_federation/ingress/validator.py`. Every field: `institution`,
`mission_id`, `cycle_id`, `timestamp`, `operating_state`,
`capability_statuses` (list of `CapabilityStatus`), `objective`,
`observations`, `findings`, `evidence_refs`, `provenance_refs`,
`uncertainty`, `limitations`, `actions_completed/rejected/failed`,
`resources`, `storage`, `cross_system_implications`, `risks`,
`recommended_next_actions`, `executive_attention_required`,
`escalation_reason`.

## Why NEXUS does not define its own parser

Per the F1 mission's explicit instruction. Maintaining a second, parallel
schema for the same message would create exactly the drift risk this whole
federation-hardening effort exists to prevent — two definitions of "what a
capability status means" that could silently diverge. `ingress/validator.py`
adds exactly one check DAT.AI's own contract does not perform for itself:
whether `schema_version` is one NEXUS has been told how to consume
(`KNOWN_SCHEMA_VERSIONS = {"1.1.0"}`).

## Fail-closed guarantee (inherited, re-verified)

Every model in DAT.AI's contract uses `extra="forbid"`. An unknown field,
an unknown enum value, or a structurally invalid combination (e.g.
`OPERATIONAL` without `external_attestation_ref`) raises
`pydantic.ValidationError` before NEXUS ever sees a partially-valid object.
Proven by `tests/failure/test_failure_modes.py::test_02_malformed_report_fails_closed`
and `test_03_unknown_schema_version_rejected`.

## When a second institution's contract differs from DAT.AI's

Not yet encountered (DAT.AI is the only real federated institution). If a
future institution's contract diverges (different field set, different
enum vocabulary), the correct response — per the same "consume directly,
don't build a parallel parser" principle — is a second explicit ingress
adapter importing *that* institution's own contract module, not a
generalized schema NEXUS invents on its own. See `FEDERATION_F2_ENTRY_CRITERIA.md`.
