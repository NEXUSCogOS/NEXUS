# DEPENDENCY GRAPH SPEC
**NEXUS Federation F2 — 2026-08-27**

## CURRENT VERIFIED IMPLEMENTATION

`dependency/model.py` defines `DependencyEdge` (source, target, edge_type,
criticality, failure_propagation, degraded_behavior) and two closed
vocabularies:

- `DependencyEdgeType`: `REQUIRES, PRODUCES, CONSUMES, PERSISTS_TO,
  VALIDATES_WITH, DELEGATES_TO, OPTIONAL_DEPENDENCY, EXTERNAL_DEPENDENCY`
- `Criticality`: `CRITICAL, DEGRADING, OPTIONAL`

`dependency/graph.py` defines the first real, hand-verified graph — 9
nodes, 9 edges — covering exactly the components proven in this mission's
DAT.AI -> NEXUS path (not an aspirational full-estate graph):

```
nexus, dat_ai, postgis, external_storage, dat_ai_model_registry,
satellite_acquisition, institutional_ingress, executive_state_store,
evidence_resolver
```

`compute_failure_propagation(edges, failed_node)` is a pure, deterministic
BFS: `REQUIRES`/`PERSISTS_TO` edges at `CRITICAL` criticality propagate
`UNAVAILABLE`; the same edge types at lower criticality, plus
`VALIDATES_WITH`, propagate only `DEGRADED`; `OPTIONAL_DEPENDENCY` and
`EXTERNAL_DEPENDENCY` edges NEVER escalate past `DEGRADED`, structurally
enforcing the mission's explicit instruction ("do not infer that optional
dependency failure means institution failure") — proven by
`test_optional_dependency_never_escalates_to_unavailable`, which checks
this for every such edge in the real graph, not just a hand-picked case.
`PRODUCES`/`CONSUMES`/`DELEGATES_TO` edges are informational only and are
never propagated as failures.

Full `DEPENDENCY_GRAPH.json` (real `model_dump()` export of every edge,
with human-readable `failure_propagation`/`degraded_behavior` text) is a
mission deliverable alongside this document.

## FOUR NAMED SCENARIOS — VERIFIED

| Scenario | Test | Result |
|---|---|---|
| PostGIS down | `test_postgis_down_degrades_dat_ai_but_nexus_still_runs` | `dat_ai=UNAVAILABLE` (matches DAT.AI's own `derive_operating_state`), `nexus=DEGRADED` (never UNAVAILABLE) |
| Satellite credentials absent | `test_satellite_credentials_absent_leaves_zoning_api_usable` | `dat_ai=DEGRADED` (never UNAVAILABLE); `nexus=DEGRADED` transitively, never UNAVAILABLE |
| DAT.AI unavailable | `test_dat_ai_unavailable_leaves_nexus_degraded_and_others_untouched` | `nexus=DEGRADED`; `institutional_ingress` absent from the result entirely (CONSUMES is never propagated) |
| Executive state store unavailable | `test_executive_state_store_unavailable_fails_ingress_closed_dat_ai_unaffected` | `institutional_ingress=UNAVAILABLE`, `nexus=UNAVAILABLE`; `dat_ai` absent from the result entirely |

The "other institutions remain unaffected" claim is proven structurally,
not asserted: an unconnected node simply never enters the BFS frontier —
`test_unconnected_hypothetical_node_never_appears` confirms this for
`evidence_resolver` (which has no outgoing edges as a source) across every
failure scenario.

## TARGET

- Extend the graph as real institutions/components are added (a second
  institution's own database, its own ingress path, etc.) — data
  additions to `dependency/graph.py`'s `EDGES` list, not changes to
  `compute_failure_propagation`'s logic.
- Wire `dependency_degradations` (currently a pass-through parameter to
  `observability/counters.compute_counters`) to an actual periodic health
  check that runs `compute_failure_propagation` against live component
  status and durably logs the result.

## LIMITATIONS

- The graph is hand-built from what this mission actually verified, not
  auto-discovered from running infrastructure. Adding a node/edge that
  doesn't reflect a real dependency would silently misrepresent failure
  propagation — there is no independent check that the graph matches
  reality beyond the human review that produced it.
- `compute_failure_propagation` only models a single node going fully
  `UNAVAILABLE`; it does not model partial degradation of the failed node
  itself propagating differently than total failure, nor does it model
  recovery/repropagation over time.
