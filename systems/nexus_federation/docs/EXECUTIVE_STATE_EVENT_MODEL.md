# EXECUTIVE STATE EVENT MODEL
**NEXUS Federation F2 — 2026-08-27**

## CURRENT VERIFIED IMPLEMENTATION

`persistence/db.py: state_event_log` is an append-only table, one row per
capability-state transition per accepted, non-duplicate ingest cycle:
`institution_id, capability_name, cycle_id, prior_lifecycle,
new_lifecycle, executive_state_class, temporal_classification,
transition_reason, evidence_refs, recorded_at`.

This coexists with, and is independent of, `institution_registry`'s
materialized "current state" (one row per institution, overwritten on
every accepted cycle). Querying `get_state_events(institution_id,
capability_name)` reconstructs the FULL history; querying
`get_registry_entry(institution_id)` returns only the latest.

`transition_reason` is always one of three deterministic strings (never a
free-text guess): `"accepted report classified {classification}"`,
`"evidence unresolved"`, or `"contradictory regression, unexplained by
findings/limitations"` — whichever applies, computed the same way
`ComponentState.executive_state_class` itself is computed, so the two can
never disagree.

### Proven

- `test_first_ingest_produces_one_event_per_capability`: cycle N with no
  prior state records `prior_lifecycle=None`.
- `test_second_ingest_reconstructs_n_and_n_plus_1`: cycle N+1 records
  `prior_lifecycle` = what cycle N reported, `new_lifecycle` = what
  changed to, plus the temporal classification and evidence refs at that
  exact moment.
- `test_contradictory_transition_recorded_with_reason`: an unexplained
  regression is recorded with the CONTRADICTORY class and a
  human-legible reason string.
- `test_duplicate_ingest_does_not_add_a_state_event`: a duplicate cycle
  adds nothing to either the materialized state or the event history.
- `test_current_materialized_state_coexists_with_immutable_history`:
  the registry shows only the latest lifecycle; the event log shows the
  full sequence that led there — both from the same two real ingests.

## TARGET

- Expose `get_state_events()` through a query surface any institution or
  operator can call directly (currently a `FederationStore` method only,
  no HTTP/CLI wrapper).
- Retention/archival policy for `state_event_log` once it grows large —
  currently unbounded and never pruned, which is correct for F1/F2's
  scale but will need an explicit policy before real production volume.

## LIMITATIONS

- State events are recorded only for capabilities present in an accepted,
  non-duplicate report — a capability an institution stops reporting
  entirely leaves no explicit "capability removed" event, only silence
  (the last real event remains the last real event, honestly, but there
  is no active signal distinguishing "still true, just not re-reported
  this cycle" from "genuinely removed").
