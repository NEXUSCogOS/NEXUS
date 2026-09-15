"""Resource budget schema.

New module, NEXUS Federation F2. Hardens F1's preliminary resource
*accounting* (observability/resource_accounting.py, which measures what a
call actually consumed) with a resource *budget* (this module, which
states what a delegation is allowed to consume before it runs).

Every dimension is mandatory and must be a finite, non-negative number.
There is deliberately no `Optional`/`None` spelling of "no limit" -- a
missing or null bound is rejected the same way an explicit
"UNBOUNDED_NOT_ALLOWED" request would be, via the same validator, with
that literal string as the rejection reason. This is a structural
prevention, not a convention: code that wants to skip stating a bound
cannot construct a valid ResourceBudget by omission.

`basis` is required and must name where the bound came from (a policy
document, a prior measurement, an explicit operator decision) -- mirroring
the `Confidence.basis` discipline in DAT.AI's own contract. A budget is
itself a claim and must be evidenced, not asserted from nowhere.
"""

from __future__ import annotations

from typing import Union

from pydantic import BaseModel, ConfigDict, field_validator

UNBOUNDED_NOT_ALLOWED = "UNBOUNDED_NOT_ALLOWED"

_NUMERIC_FIELDS = (
    "cpu_seconds",
    "memory_bytes",
    "elapsed_seconds",
    "local_storage_bytes",
    "external_storage_bytes",
    "api_cost_usd",
    "model_tokens",
)


class ResourceBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu_seconds: float
    memory_bytes: int
    elapsed_seconds: float
    local_storage_bytes: int
    external_storage_bytes: int
    api_cost_usd: float
    model_tokens: int
    basis: str  # policy reference / prior measurement this bound derives from -- never fabricated

    @field_validator(*_NUMERIC_FIELDS, mode="before")
    @classmethod
    def _reject_unbounded(cls, v):
        if v is None:
            raise ValueError(
                f"{UNBOUNDED_NOT_ALLOWED}: every resource budget dimension "
                f"must carry an explicit finite bound -- a delegation may "
                f"not be issued with an unstated or unlimited resource cap"
            )
        return v

    @field_validator(*_NUMERIC_FIELDS)
    @classmethod
    def _reject_negative(cls, v):
        if v < 0:
            raise ValueError("resource budget dimensions must be non-negative")
        return v

    @field_validator("basis")
    @classmethod
    def _basis_required(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("resource budget requires a stated basis, never a fabricated bound")
        return v


# A conservative, named default for the one delegation category currently
# ever issued by this federation (ANALYSE-only, no external calls, no
# model tokens) -- deliberately small, explicitly justified, never silently
# assumed to be "big enough for anything."
DEFAULT_ANALYSIS_ONLY_BUDGET = ResourceBudget(
    cpu_seconds=30.0,
    memory_bytes=512 * 1024 * 1024,
    elapsed_seconds=300.0,
    local_storage_bytes=10 * 1024 * 1024,
    external_storage_bytes=0,
    api_cost_usd=0.0,
    model_tokens=0,
    basis=(
        "NEXUS Federation F2 policy default for ANALYSE-authority delegations: "
        "no external storage, no API cost, no model tokens, because the only "
        "delegation category issued this phase (relevance/router.py "
        "ROUTING_TABLE) requests analysis of already-supplied evidence only"
    ),
)
