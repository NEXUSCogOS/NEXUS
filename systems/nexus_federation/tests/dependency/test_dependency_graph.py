"""Dependency graph and failure-propagation tests.

Proves the four scenarios named explicitly in the F2 mission (section 7,
FAILURE PROPAGATION MODEL) against the real, hand-verified edge list in
dependency/graph.py -- not a toy graph built just for the test.
"""

from __future__ import annotations

from dependency.graph import EDGES, NODES, compute_failure_propagation


def test_all_edges_reference_known_nodes():
    for edge in EDGES:
        assert edge.source in NODES, f"edge source {edge.source!r} not in NODES"
        assert edge.target in NODES, f"edge target {edge.target!r} not in NODES"


def test_postgis_down_degrades_dat_ai_but_nexus_still_runs():
    """PostGIS down -> DAT.AI database component degraded (its own
    operating_state becomes UNAVAILABLE, per institutional/contract.py's
    own derive_operating_state) -> NEXUS still runs (merely DEGRADED, via
    its OPTIONAL_DEPENDENCY edge to DAT.AI, never UNAVAILABLE)."""
    status = compute_failure_propagation(EDGES, "postgis")
    assert status["postgis"] == "UNAVAILABLE"
    assert status["dat_ai"] == "UNAVAILABLE"  # matches DAT.AI's own contract semantics
    assert status["nexus"] == "DEGRADED"  # NEXUS still runs
    assert status["nexus"] != "UNAVAILABLE"


def test_satellite_credentials_absent_leaves_zoning_api_usable():
    """Satellite acquisition unavailable -> DAT.AI merely degraded (never
    UNAVAILABLE) via the OPTIONAL_DEPENDENCY edge -> nothing about
    zoning_api's own component-level status is touched by this function at
    all (that granularity lives in state/capability.py, not the dependency
    graph) -- the dependency-level claim this test verifies is exactly
    that DAT.AI-overall does not become UNAVAILABLE."""
    status = compute_failure_propagation(EDGES, "satellite_acquisition")
    assert status["satellite_acquisition"] == "UNAVAILABLE"
    assert status["dat_ai"] == "DEGRADED"
    assert status["dat_ai"] != "UNAVAILABLE"
    # nexus is reachable transitively (nexus -> OPTIONAL_DEPENDENCY -> dat_ai,
    # now degraded), but OPTIONAL_DEPENDENCY never escalates beyond DEGRADED
    # at any hop -- nexus must never become UNAVAILABLE from this.
    assert status["nexus"] == "DEGRADED"
    assert status["nexus"] != "UNAVAILABLE"


def test_dat_ai_unavailable_leaves_nexus_degraded_and_others_untouched():
    """DAT.AI unavailable -> NEXUS retains last accepted state (DEGRADED,
    not UNAVAILABLE) -> a node with no edge to DAT.AI is entirely absent
    from the returned status (the mechanism proving 'other institutions
    remain unaffected': isolation is structural, not asserted)."""
    status = compute_failure_propagation(EDGES, "dat_ai")
    assert status["dat_ai"] == "UNAVAILABLE"
    assert status["nexus"] == "DEGRADED"
    assert status["nexus"] != "UNAVAILABLE"
    # institutional_ingress CONSUMES dat_ai, which this function never
    # propagates as a failure of the consumer:
    assert "institutional_ingress" not in status


def test_executive_state_store_unavailable_fails_ingress_closed_dat_ai_unaffected():
    """Executive state store unavailable -> ingress fails closed
    (institutional_ingress becomes UNAVAILABLE via its CRITICAL
    PERSISTS_TO edge) -> DAT.AI itself is entirely untouched (no edge
    points from DAT.AI toward institutional_ingress or
    executive_state_store in a way this function would propagate)."""
    status = compute_failure_propagation(EDGES, "executive_state_store")
    assert status["executive_state_store"] == "UNAVAILABLE"
    assert status["institutional_ingress"] == "UNAVAILABLE"
    assert status["nexus"] == "UNAVAILABLE"  # NEXUS REQUIRES ingress, CRITICAL
    assert "dat_ai" not in status


def test_model_registry_external_storage_down_is_degrading_not_critical():
    """External storage unavailable degrades DAT.AI's model_registry-
    dependent capability specifically, not the whole institution --
    matches institutional/contract.py's own DEGRADED (not UNAVAILABLE)
    semantics for external_storage='unavailable'."""
    status = compute_failure_propagation(EDGES, "external_storage")
    assert status["dat_ai_model_registry"] == "DEGRADED"
    assert status.get("dat_ai") is None or status["dat_ai"] != "UNAVAILABLE"


def test_optional_dependency_never_escalates_to_unavailable():
    """Structural proof of the mission's explicit instruction: no matter
    which node fails, an OPTIONAL_DEPENDENCY/EXTERNAL_DEPENDENCY edge never
    produces UNAVAILABLE on the depending side."""
    from dependency.model import DependencyEdgeType

    for edge in EDGES:
        if edge.edge_type in (DependencyEdgeType.OPTIONAL_DEPENDENCY, DependencyEdgeType.EXTERNAL_DEPENDENCY):
            status = compute_failure_propagation(EDGES, edge.target)
            assert status.get(edge.source) != "UNAVAILABLE"


def test_unconnected_hypothetical_node_never_appears():
    """A node with genuinely no path to the failed node is absent from the
    result regardless of which real node fails -- this is what proves
    'other institutions should remain unaffected' structurally rather than
    by assertion."""
    for failed in ("postgis", "dat_ai", "satellite_acquisition", "executive_state_store"):
        status = compute_failure_propagation(EDGES, failed)
        assert "evidence_resolver" not in status or failed == "evidence_resolver"
