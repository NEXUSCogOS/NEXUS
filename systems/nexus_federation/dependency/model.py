"""Dependency graph typed model.

New module, NEXUS Federation F2.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class DependencyEdgeType(str, Enum):
    REQUIRES = "REQUIRES"
    PRODUCES = "PRODUCES"
    CONSUMES = "CONSUMES"
    PERSISTS_TO = "PERSISTS_TO"
    VALIDATES_WITH = "VALIDATES_WITH"
    DELEGATES_TO = "DELEGATES_TO"
    OPTIONAL_DEPENDENCY = "OPTIONAL_DEPENDENCY"
    EXTERNAL_DEPENDENCY = "EXTERNAL_DEPENDENCY"


class Criticality(str, Enum):
    CRITICAL = "CRITICAL"    # target unavailable -> source unavailable
    DEGRADING = "DEGRADING"  # target unavailable -> source degraded, not unavailable
    OPTIONAL = "OPTIONAL"    # target unavailable -> source at most degraded; failure never inferred as source failure


class DependencyEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    edge_type: DependencyEdgeType
    criticality: Criticality
    failure_propagation: str  # human-readable description of what happens to `source` if `target` fails
    degraded_behavior: str  # human-readable description of what remains usable
