"""NEXUS executive state classification.

New module, NEXUS Federation F1. Distinguishes how NEXUS itself knows what
it knows about a given piece of institutional state -- separate from, and
layered on top of, the institution's own self-reported capability lifecycle.

This is deliberately conservative: NEXUS does not independently re-verify
any institution's internal checks this phase (it has no DB access into
DAT.AI's PostGIS, for instance). The honest ceiling for anything ingested
through the federation ingress is therefore DERIVED, never OBSERVED --
OBSERVED is reserved for a future phase where NEXUS performs its own
independent verification of a claim, which does not exist yet.
"""

from __future__ import annotations

from enum import Enum


class ExecutiveStateClass(str, Enum):
    """How NEXUS knows this, not what the institution claims."""

    OBSERVED = "OBSERVED"  # NEXUS independently re-verified the underlying evidence itself
    DERIVED = "DERIVED"  # computed from the institution's own accepted, evidenced report
    INFERRED = "INFERRED"  # NEXUS drew a conclusion beyond what any single report directly states
    PREDICTED = "PREDICTED"  # a forward projection, not yet true
    UNKNOWN = "UNKNOWN"  # no evidence available, or evidence failed to resolve
    STALE = "STALE"  # was known with some class above, now aged past a threshold
    CONTRADICTORY = "CONTRADICTORY"  # conflicting claims across reports, not silently resolved


# NEXUS Federation F1 never independently re-verifies an institution's own
# infrastructure (that would require NEXUS to hold live credentials/DB
# access into every federated institution, out of this mission's scope).
# This constant documents that ceiling so it cannot be silently exceeded by
# a future edit without a deliberate, visible change here.
MAX_REACHABLE_CLASS_THIS_PHASE = ExecutiveStateClass.DERIVED
