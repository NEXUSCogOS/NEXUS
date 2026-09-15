"""The first real NEXUS Federation dependency graph.

New module, NEXUS Federation F2. A small, hand-verified graph of the
components actually involved in the DAT.AI -> NEXUS path proven in F1/F2 --
not an aspirational full-estate graph. Every edge below corresponds to a
dependency this codebase (or DAT.AI's own, already-verified architecture)
actually has; none is speculative.

`compute_failure_propagation` is a pure, deterministic function over this
edge list. It never infers that an OPTIONAL_DEPENDENCY or
EXTERNAL_DEPENDENCY failure means the depending node has failed -- those
edge types cap propagation at DEGRADED, matching the mission's explicit
instruction: "Do not infer that optional dependency failure means
institution failure."
"""

from __future__ import annotations

from dependency.model import Criticality, DependencyEdge, DependencyEdgeType

NODES: list[str] = [
    "nexus",
    "dat_ai",
    "postgis",
    "external_storage",
    "dat_ai_model_registry",
    "satellite_acquisition",
    "institutional_ingress",
    "executive_state_store",
    "evidence_resolver",
]

EDGES: list[DependencyEdge] = [
    DependencyEdge(
        source="dat_ai",
        target="postgis",
        edge_type=DependencyEdgeType.REQUIRES,
        criticality=Criticality.CRITICAL,
        failure_propagation=(
            "PostGIS unavailable makes DAT.AI's own operating_state UNAVAILABLE "
            "(institutional/contract.py derive_operating_state: database/postgis "
            "unhealthy -> UNAVAILABLE) -- the database is not an optional part of "
            "DAT.AI's core zoning capability."
        ),
        degraded_behavior="No DAT.AI capability functions without its database.",
    ),
    DependencyEdge(
        source="dat_ai",
        target="satellite_acquisition",
        edge_type=DependencyEdgeType.OPTIONAL_DEPENDENCY,
        criticality=Criticality.OPTIONAL,
        failure_propagation=(
            "Satellite acquisition credentials being absent leaves DAT.AI "
            "overall merely degraded (one capability reports "
            "EXTERNAL_DEPENDENCY_UNAVAILABLE); it never fails DAT.AI's other "
            "capabilities."
        ),
        degraded_behavior="zoning_api, model_registry, promotion_gate all remain usable.",
    ),
    DependencyEdge(
        source="dat_ai_model_registry",
        target="external_storage",
        edge_type=DependencyEdgeType.REQUIRES,
        criticality=Criticality.DEGRADING,
        failure_propagation=(
            "External storage unavailable makes DAT.AI's operating_state "
            "DEGRADED (not UNAVAILABLE) per derive_operating_state -- the "
            "model file being unreachable degrades classification capability "
            "specifically, not the whole institution."
        ),
        degraded_behavior="zoning_api (no dependency on the model file) remains usable.",
    ),
    DependencyEdge(
        source="dat_ai",
        target="dat_ai_model_registry",
        edge_type=DependencyEdgeType.CONSUMES,
        criticality=Criticality.OPTIONAL,
        failure_propagation="Informational only -- CONSUMES edges are not propagated as failures by this function.",
        degraded_behavior="n/a",
    ),
    DependencyEdge(
        source="institutional_ingress",
        target="dat_ai",
        edge_type=DependencyEdgeType.CONSUMES,
        criticality=Criticality.OPTIONAL,
        failure_propagation=(
            "Ingress consuming a report is a one-way pull; ingress failing "
            "does not fail DAT.AI (DAT.AI has no edge depending on ingress), "
            "and DAT.AI failing does not fail ingress by this edge alone "
            "(see the separate nexus->dat_ai OPTIONAL_DEPENDENCY edge for the "
            "actual effect on NEXUS)."
        ),
        degraded_behavior="n/a -- CONSUMES edges are not propagated as failures by this function.",
    ),
    DependencyEdge(
        source="institutional_ingress",
        target="evidence_resolver",
        edge_type=DependencyEdgeType.VALIDATES_WITH,
        criticality=Criticality.DEGRADING,
        failure_propagation=(
            "Evidence resolver unavailable degrades ingress (capability "
            "claims can no longer be resolved against real evidence -> "
            "executive_state_class falls to UNKNOWN per state/executive_state.py), "
            "but reports are still schema-validated and persisted."
        ),
        degraded_behavior="Schema validation, temporal classification, and persistence continue.",
    ),
    DependencyEdge(
        source="institutional_ingress",
        target="executive_state_store",
        edge_type=DependencyEdgeType.PERSISTS_TO,
        criticality=Criticality.CRITICAL,
        failure_propagation=(
            "Executive state store unavailable means ingress cannot durably "
            "record an accepted report at all -- it must fail closed rather "
            "than accept a report it cannot persist."
        ),
        degraded_behavior="No new reports can be accepted; DAT.AI itself is entirely unaffected by this.",
    ),
    DependencyEdge(
        source="nexus",
        target="institutional_ingress",
        edge_type=DependencyEdgeType.REQUIRES,
        criticality=Criticality.CRITICAL,
        failure_propagation="Ingress is NEXUS's only accepted entry point for institutional state.",
        degraded_behavior="n/a",
    ),
    DependencyEdge(
        source="nexus",
        target="dat_ai",
        edge_type=DependencyEdgeType.OPTIONAL_DEPENDENCY,
        criticality=Criticality.OPTIONAL,
        failure_propagation=(
            "DAT.AI unavailable leaves NEXUS merely degraded: it retains the "
            "last accepted state for dat_ai, which becomes STALE/EXPIRED over "
            "time via state/temporal.classify_age_only, but NEXUS itself keeps "
            "running and other institutions' registry entries are untouched."
        ),
        degraded_behavior="Other institutions' state, ingress, and delegation logic remain fully operative.",
    ),
]


def get_edges() -> list[DependencyEdge]:
    return list(EDGES)


def compute_failure_propagation(edges: list[DependencyEdge], failed_node: str) -> dict[str, str]:
    """Given a node that has gone fully unavailable, compute the bounded
    set of other nodes affected, and how.

    Returns {node_id: status}, status in {"UNAVAILABLE", "DEGRADED"}.
    `failed_node` itself is included as "UNAVAILABLE". A node not present
    in the returned dict is unaffected -- this is the mechanism by which
    "other institutions should remain unaffected" is proven: an
    unconnected node simply never enters the BFS frontier.
    """
    status: dict[str, str] = {failed_node: "UNAVAILABLE"}
    frontier = {failed_node}

    while frontier:
        next_frontier: set[str] = set()
        for edge in edges:
            if edge.target not in status or edge.source in status:
                continue
            target_state = status[edge.target]

            if edge.edge_type in (
                DependencyEdgeType.OPTIONAL_DEPENDENCY,
                DependencyEdgeType.EXTERNAL_DEPENDENCY,
            ):
                # Never escalate an optional/external dependency failure
                # into a full failure of the thing that depends on it.
                new_state = "DEGRADED"
            elif edge.edge_type in (
                DependencyEdgeType.REQUIRES,
                DependencyEdgeType.PERSISTS_TO,
            ):
                if edge.criticality == Criticality.CRITICAL:
                    new_state = "UNAVAILABLE" if target_state == "UNAVAILABLE" else "DEGRADED"
                else:  # DEGRADING or OPTIONAL criticality on a REQUIRES/PERSISTS_TO edge
                    new_state = "DEGRADED"
            elif edge.edge_type == DependencyEdgeType.VALIDATES_WITH:
                new_state = "DEGRADED"
            else:
                # PRODUCES, CONSUMES, DELEGATES_TO: informational, not
                # propagated as a failure of the source by this function.
                continue

            status[edge.source] = new_state
            next_frontier.add(edge.source)
        frontier = next_frontier

    return status
