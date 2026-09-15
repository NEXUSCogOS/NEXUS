"""Federation ingress: schema/version validation.

New module, NEXUS Federation F1, generalized in F2.

Per the mission's explicit instruction, this module consumes an
institution's own contract module DIRECTLY -- it does not reimplement,
wrap, or approximate the schema. For DAT.AI, that is
`institutional.contract` (importable here because both `systems/dat_ai`
and `systems/nexus_federation` are on PYTHONPATH when the federation runs
-- see FEDERATION_INGRESS_ARCHITECTURE.md for why this is the chosen
mechanism rather than a network/message-bus transport, which does not
exist anywhere in this estate yet).

NEXUS Federation F2: dispatch is no longer hardcoded to DAT.AI's module.
`ingress/contract_registry.py` maps `institution_id -> (validate_fn,
known_schema_versions)`; this module looks up the incoming payload's
`institution` field in that registry BEFORE attempting any validation. An
institution_id with no registered contract is rejected, fail-closed, with
a clear reason -- never silently routed to the wrong validator or
silently accepted. Adding a second real institution is a registry
addition (ingress/contract_registry.py), not a change to the dispatch
logic here -- see SECOND_INSTITUTION_ENTRY_PROTOCOL.md and
tests/contract/test_second_institution_generic.py.

A registered `validate_fn` already fails closed on any malformed payload
for its own institution (DAT.AI's `validate_report()` does, because every
model in `institutional.contract` uses `extra="forbid"`); this module adds
exactly one universal check no per-institution contract does for itself:
whether the incoming `schema_version` matches a version that specific
institution's registration says NEXUS knows how to consume.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ingress.contract_registry import get_contract


@dataclass(frozen=True)
class IngressResult:
    accepted: bool
    report: Optional[Any]
    reason: str


def ingest_raw_payload(payload: dict[str, Any]) -> IngressResult:
    """The one entry point for anything arriving at the federation ingress.

    Order of checks: (1) is there a registered contract for this
    `institution` at all; (2) does `schema_version` match a version that
    institution's registration recognizes; (3) full validation via that
    institution's own validate_fn. An unrecognized institution or version
    is rejected explicitly and distinctly, never silently coerced into
    "close enough."
    """
    institution_id = payload.get("institution")
    registration = get_contract(institution_id) if isinstance(institution_id, str) else None
    if registration is None:
        return IngressResult(
            accepted=False,
            report=None,
            reason=f"no registered contract for institution {institution_id!r} -- rejected, not silently accepted",
        )

    raw_version = payload.get("schema_version")
    if raw_version not in registration.known_schema_versions:
        return IngressResult(
            accepted=False,
            report=None,
            reason=(
                f"unknown schema_version {raw_version!r} for institution {institution_id!r}, "
                f"rejected (known_schema_versions={sorted(registration.known_schema_versions)})"
            ),
        )

    try:
        report = registration.validate_fn(payload)
    except Exception as exc:  # noqa: BLE001 -- reported, not swallowed
        return IngressResult(
            accepted=False,
            report=None,
            reason=f"schema validation failed: {type(exc).__name__}: {exc}",
        )

    return IngressResult(accepted=True, report=report, reason="schema-valid")
