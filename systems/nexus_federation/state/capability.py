"""NEXUS-side capability state model.

New module, NEXUS Federation F1. Wraps an institution's own self-reported
capability lifecycle (which NEXUS never re-derives or overrides) together
with NEXUS's separate executive-state classification of how well-evidenced
that claim is, and whether the underlying evidence actually resolved.

Per the mission's explicit prohibition, this module never infers
IMPLEMENTED -> OPERATIONAL or INTEGRATED -> EMPIRICALLY_VALIDATED, and
never collapses per-capability granularity into one boolean.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from state.executive_state import ExecutiveStateClass
from state.temporal import TemporalClassification

# The capability lifecycle vocabulary is owned by the reporting institution
# (DAT.AI defines it in institutional/contract.py). NEXUS consumes whatever
# string an institution reports and never invents a different vocabulary --
# consuming DAT.AI's existing contract directly rather than building a
# parallel enum keeps NEXUS from silently diverging from what institutions
# actually say. NEXUS treats the value as an opaque string for storage and
# comparison purposes (see registry/models.py) rather than importing
# DAT.AI's Python enum directly, so that a future, differently-shaped
# institution is not forced through DAT.AI's specific type.

_LIFECYCLE_LADDER = [
    "NOT_IMPLEMENTED",
    "IMPLEMENTED",
    "TESTED",
    "INTEGRATED",
    "EMPIRICALLY_VALIDATED",
    "OPERATIONAL",
]
# NOT_COMMISSIONED, EXTERNAL_DEPENDENCY_UNAVAILABLE, DEGRADED, UNKNOWN are
# explicitly NOT on this ladder -- they are terminal/side states, not points
# of progress, and a transition into or out of them is never treated as a
# "regression" or "advance" for contradiction-detection purposes.


def lifecycle_rank(lifecycle: str) -> Optional[int]:
    """Position on the maturity ladder, or None if it's a side-state."""
    try:
        return _LIFECYCLE_LADDER.index(lifecycle)
    except ValueError:
        return None


class ComponentState(BaseModel):
    """One capability's full state as NEXUS holds it."""

    model_config = ConfigDict(extra="forbid")

    capability_name: str
    reported_lifecycle: str  # exactly as the institution reported it -- never rewritten
    executive_state_class: ExecutiveStateClass
    evidence_refs: list[str] = Field(default_factory=list)
    evidence_resolved: bool
    unresolved_evidence_refs: list[str] = Field(default_factory=list)
    last_updated_cycle: str
    last_updated_timestamp: str
    temporal_classification: TemporalClassification
    detail: str = ""
