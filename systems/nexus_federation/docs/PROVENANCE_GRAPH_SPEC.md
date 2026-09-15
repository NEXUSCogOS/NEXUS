# PROVENANCE GRAPH SPEC
**NEXUS Federation F2 — 2026-08-27**

## CURRENT VERIFIED IMPLEMENTATION

`provenance/model.py` defines `ProvenanceRecord`: a versioned, structured
record with `provenance_id`, `source_type`, `source_uri_or_path`,
`source_hash`, `source_timestamp`, `observation_timestamp`,
`ingestion_timestamp`, `producer`, `method`, `parent_provenance_ids`,
`verification_status` (`VERIFIED | PARTIAL | UNVERIFIED | INVALID |
MISSING`), and `verification_method`. `VERIFIED` and `INVALID` both
require a stated `verification_method` — a verified or invalidated claim
without a stated method is rejected at construction time (pydantic
validator), not merely discouraged.

Records are append-only (`persistence/db.py: provenance_record` table,
insert-only, no update method exists). `provenance/graph.py` provides
`trace_back()` (walks `parent_provenance_ids` recursively, cycle-safe,
root-first order) and `explain()` (human-readable rendering of that
chain), plus `root_verification_status()` (the verification status of the
ULTIMATE source, which may differ from a downstream record's own status).

### The real, proven chain

```
source_evidence_file  (producer: the institution, e.g. dat_ai)
        |
institutional_report  (producer: the institution; parent = every capability's evidence records)
        |
nexus_executive_state (producer: nexus_federation; parent = institutional_report)
        |
delegation_proposal   (producer: nexus_federation.relevance_router; parent = nexus_executive_state)
```

Verified end-to-end via a real `FederationKernel.ingest_report()` call
with a real relevance signal in this mission (see
`DAT_AI_TO_NEXUS_E2E_EVIDENCE.md` / mission evidence): 4 records, 4 hops,
`root_verification_status = PARTIAL` (first-sighting evidence, no
independent expected hash to compare against — an honest PARTIAL, not a
fabricated VERIFIED), `leaf_verification_status = VERIFIED` (the
delegation's own construction is deterministic and directly checkable).

`KernelResult.provenance_ids` exposes one `nexus_executive_state`
provenance id per capability per ingest, so any caller can immediately
answer "why does this executive state exist?" by tracing backward.

## TARGET

The full chain the mission describes:

```
source document/data -> DAT.AI ingestion -> canonical spatial entity ->
DAT.AI finding -> InstitutionalReport -> NEXUS executive state ->
DelegationProposal
```

## LIMITATIONS

**DAT.AI does not yet expose row-level provenance across the federation
boundary.** DAT.AI's own database rows (e.g. `PlanningZone`,
`SatelliteChange`) have internal provenance columns (`data_source`,
`source_confidence`, `verified_at` — see `migrations/003_satellite_provenance.sql`),
but NOTHING in DAT.AI's `InstitutionalReport` contract today carries a
reference NEXUS could resolve back to a specific database row or a
specific ingestion event inside DAT.AI's own pipeline. The chain NEXUS
can currently build honestly begins at the evidence ARTIFACT it can
itself see (a file NEXUS can hash and check) — not at DAT.AI's internal
"ingestion" or "canonical spatial entity" steps, which remain opaque to
NEXUS in this phase.

Closing this gap requires DAT.AI's own contract to add a structured
`provenance_refs` field carrying row-level identifiers (see
`PROVENANCE_STANDARD.md`'s own stated gap, carried into F2 as
`SECOND_INSTITUTION_ENTRY_PROTOCOL.md`'s explicit requirement for any
future institution) — this is a DAT.AI-side (or future institution-side)
change, not something NEXUS's ingress can manufacture on its own without
fabricating a link that doesn't really exist.
