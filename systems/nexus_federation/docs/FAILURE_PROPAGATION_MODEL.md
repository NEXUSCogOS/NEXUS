# FAILURE PROPAGATION MODEL
**NEXUS Federation F2 — 2026-08-27**

See `DEPENDENCY_GRAPH_SPEC.md` for the underlying graph and edge
semantics. This document focuses on the propagation ALGORITHM and its
proven behavior.

## CURRENT VERIFIED IMPLEMENTATION

`dependency/graph.py: compute_failure_propagation(edges, failed_node)` —
a breadth-first traversal starting from one node marked `UNAVAILABLE`,
computing status for every node reachable via an edge whose semantics
imply the source depends on the target's availability:

| Edge type | Criticality | Target UNAVAILABLE -> Source becomes |
|---|---|---|
| `REQUIRES` / `PERSISTS_TO` | `CRITICAL` | `UNAVAILABLE` |
| `REQUIRES` / `PERSISTS_TO` | `DEGRADING` / `OPTIONAL` | `DEGRADED` |
| `VALIDATES_WITH` | any | `DEGRADED` |
| `OPTIONAL_DEPENDENCY` / `EXTERNAL_DEPENDENCY` | any | `DEGRADED`, never `UNAVAILABLE` |
| `PRODUCES` / `CONSUMES` / `DELEGATES_TO` | any | not propagated (informational only) |

A node with no incoming propagating edge from the failed node never
appears in the result at all — this is the mechanism, not an assertion,
by which unrelated institutions/components are proven unaffected.

Bounded impact is computed, not estimated: `compute_failure_propagation`
is a pure function over the real edge list, exercised directly by tests,
producing exact status strings — never a fabricated severity score.

## FOUR NAMED EXAMPLES — VERIFIED

See `DEPENDENCY_GRAPH_SPEC.md`'s scenario table for the exact assertions;
summarized:

1. **PostGIS down** -> `dat_ai=UNAVAILABLE`, `nexus=DEGRADED` (never
   UNAVAILABLE) — NEXUS still runs.
2. **Satellite credentials absent** -> `dat_ai=DEGRADED` (never
   UNAVAILABLE) — zoning_api remains usable.
3. **DAT.AI unavailable** -> `nexus=DEGRADED` (retains last accepted
   state, which becomes STALE over time via `state/temporal.py`, a
   SEPARATE mechanism from this graph) — other institutions structurally
   untouched.
4. **Executive state store unavailable** -> `institutional_ingress` and
   `nexus` become `UNAVAILABLE` (fails closed, correctly) — `dat_ai`
   structurally untouched.

## TARGET

- Combine this static graph-based propagation with LIVE component health
  checks (today: the four scenarios are proven against the static graph
  directly; nothing yet polls real component health and feeds it through
  `compute_failure_propagation` automatically on a schedule).
- Feed `dependency_degradations` (an `observability/counters.py` counter
  that currently accepts an externally-supplied value) from that live
  polling loop once it exists.

## LIMITATIONS

- This models ONE node failing at a time. Simultaneous multi-node failure
  is not modeled — the BFS would need to be seeded with multiple failed
  nodes to reason about that, which has not been implemented or tested.
- No time dimension: the model answers "what breaks NOW if X is down,"
  not "how does the blast radius change if X stays down for an hour."
