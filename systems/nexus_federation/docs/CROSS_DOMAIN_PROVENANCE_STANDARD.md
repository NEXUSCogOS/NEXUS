# CROSS-DOMAIN PROVENANCE STANDARD
**NEXUS Federation F6 — 2026-08-28**

## Required identifiers, per mission section 17

Every hop below must be a real, persistent identifier — never a
placeholder label. Verified in `F6_PROVENANCE_GRAPH.json` (captured from
one real execution) and in
`test_f6_why_what_how_reconstructible_from_stored_evidence`.

### Chain 1: Librarian

```
DAT.AI source evidence  -> planning_zones:project_id=camduong
                            (real row, real government-sourced geometry)
  -> DAT.AI finding      -> DAT.AI report_id (real UUID, kernel-accepted)
    -> NEXUS trigger     -> trigger_id (deterministic UUID5, NOT random --
                            see F6_REPRODUCIBILITY_PROTOCOL.md)
      -> Librarian delegation -> delegation_id (deterministic UUID5)
        -> Librarian source evidence -> arxiv:<id> (real corpus identifiers)
          -> Librarian synthesis -> claim_class + basis_for_status
            -> Librarian report -> report_id (real UUID)
              -> NEXUS (ingested) -> kernel.ingest_report() result
```

### Chain 2: Sentinel

```
DAT.AI finding -> NEXUS trigger -> Sentinel delegation
  -> market record(s) -> companies:symbol=<ticker>,
                          prices_daily:symbol=<ticker>:date=<date>,
                          frontier_decisions:symbol=<ticker>
    -> Sentinel derived metrics -> entity_mappings (classification + basis)
      -> Sentinel report -> report_id (real UUID)
        -> NEXUS (ingested) -> kernel.ingest_report() result
```

### Chain 3: Synthesis

```
both reports -> executive synthesis -> synthesis_id (fresh UUID per computation)
  -> executive state event -> state_event_log row, cycle_id =
     "identity:<sorted report_id pair>:<synthesis_id of the FIRST run
     that produced this identity>"
```

## Why the trigger_id is deterministic, not random

A random `trigger_id` per Process A invocation would mean a replay
against the identical DAT.AI evidence produces a DIFFERENT trigger, and
therefore different delegation_ids — defeating idempotency (mission
section 23) structurally, not just by omission. `trigger_id =
uuid5(NAMESPACE_URL, f"f6-trigger:{dat_ai_cycle_id}:{zone_project_id}")`
— the same two inputs always produce the same trigger_id, which is what
makes replay detection possible at all.

## Why the synthesis_id is NOT deterministic

Unlike `trigger_id`, `synthesis_id` is a fresh UUID on every
`synthesize()` call by design — synthesis is a pure computation, useful
to re-run for debugging/logging even when nothing new should be
persisted. The DEDUPLICATION key for persistence is a separately
computed `identity:<sorted report_id pair>` prefix on the
`state_event_log.cycle_id`, checked before writing. See
NEXUS_EXECUTIVE_SYNTHESIS_MODEL.md.
