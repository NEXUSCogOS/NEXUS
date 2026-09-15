"""Per-institution contract registry.

New module, NEXUS Federation F2. F1's ingress hardcoded a direct import of
DAT.AI's own `institutional.contract` module -- correct for F1 (only one
real institution existed, and the mission explicitly wanted DAT.AI's
contract consumed directly rather than a NEXUS-side re-parser), but it
meant the validation step itself was DAT.AI-specific: DAT.AI's own
`InstitutionalReport.institution` field is `Literal["dat_ai"]`, so no
other institution's report could ever validate through that path,
regardless of anything on the NEXUS side.

This module makes that coupling explicit and swappable: a small registry
mapping `institution_id -> (validate_fn, known_schema_versions)`. Adding a
second real institution means registering its own contract module's
validate function here -- a data addition, not a change to
`ingress/validator.py`'s logic. An institution_id with no registered
contract is rejected, fail-closed, with a clear reason -- never silently
accepted or silently routed to the wrong validator.

`register_test_fixture_contract()` exists ONLY for the F2
contract-generality test (tests/contract/test_second_institution_generic.py)
proving this dispatch mechanism itself needs no code change to accept a
second, differently-shaped institution -- it is not a claim that any such
institution is real or connected.
"""

from __future__ import annotations

from typing import Any, Callable, NamedTuple

from institutional.contract import InstitutionalReport, validate_report
from contracts.generic import validate_report as validate_generic_report


class ContractRegistration(NamedTuple):
    validate_fn: Callable[[dict[str, Any]], Any]
    known_schema_versions: frozenset[str]


_REGISTRY: dict[str, ContractRegistration] = {
    "dat_ai": ContractRegistration(validate_fn=validate_report, known_schema_versions=frozenset({"1.1.0"})),
    # NEXUS Federation F3: Librarian is the first real institution to use
    # the GENERIC federation contract (institutional/generic_contract.py)
    # rather than a bespoke, institution-owned module -- per the F3
    # mission's explicit instruction not to build a Librarian-specific
    # federation parser. See SECOND_INSTITUTION_ENTRY_PROTOCOL.md and
    # LIBRARIAN_INSTITUTIONAL_CONTRACT.md.
    "librarian": ContractRegistration(validate_fn=validate_generic_report, known_schema_versions=frozenset({"1.0.0"})),
    # NEXUS Federation F4C: NEXUS is the executive institution using the
    # same GENERIC contract. This enables real delegation cycles where NEXUS
    # can consume reports from specialist institutions (DAT.AI, Librarian)
    # using a consistent, extensible schema.
    "nexus": ContractRegistration(validate_fn=validate_generic_report, known_schema_versions=frozenset({"1.0.0"})),
    # NEXUS Federation F5: Sentinel (financial intelligence) is the third
    # specialist institution, also on the GENERIC contract -- no
    # Sentinel-specific federation parser, per the same discipline as
    # Librarian. See SENTINEL_INSTITUTIONAL_CONTRACT.md.
    "sentinel": ContractRegistration(validate_fn=validate_generic_report, known_schema_versions=frozenset({"1.0.0"})),
    # NEXUS Federation F7: News/Media Intelligence is the fourth
    # specialist institution, also on the GENERIC contract -- no
    # News-specific federation parser. See NEWS_INSTITUTIONAL_CONTRACT.md.
    "news_intelligence": ContractRegistration(validate_fn=validate_generic_report, known_schema_versions=frozenset({"1.0.0"})),
    # NEXUS Federation F8: YouTube Production is the fifth specialist
    # institution, also on the GENERIC contract -- no YouTube-specific
    # federation parser. See YOUTUBE_INSTITUTIONAL_CONTRACT.md.
    "youtube_production": ContractRegistration(validate_fn=validate_generic_report, known_schema_versions=frozenset({"1.0.0"})),
}


def get_contract(institution_id: str) -> ContractRegistration | None:
    return _REGISTRY.get(institution_id)


def register_contract(institution_id: str, validate_fn: Callable[[dict[str, Any]], Any], known_schema_versions: frozenset[str]) -> None:
    """Register a new institution's contract. Intended for real
    onboarding of a second institution (F3+) or for test doubles -- never
    called with a fabricated/unverified validator in production code."""
    _REGISTRY[institution_id] = ContractRegistration(validate_fn, known_schema_versions)


def unregister_contract(institution_id: str) -> None:
    _REGISTRY.pop(institution_id, None)


def known_institution_ids() -> frozenset[str]:
    return frozenset(_REGISTRY.keys())


def bootstrap_federation_registry() -> None:
    """Ensure canonical federation institutions are registered.

    Called once at process startup to guarantee NEXUS, Librarian, and DAT.AI
    are available for delegation and report ingestion. This is the canonical
    bootstrap path used by all subprocess orchestration.

    Idempotent: safe to call multiple times.
    """
    register_contract("nexus", validate_generic_report, frozenset({"1.0.0"}))
    register_contract("librarian", validate_generic_report, frozenset({"1.0.0"}))
    register_contract("dat_ai", validate_report, frozenset({"1.1.0"}))
    register_contract("sentinel", validate_generic_report, frozenset({"1.0.0"}))
    register_contract("news_intelligence", validate_generic_report, frozenset({"1.0.0"}))
    register_contract("youtube_production", validate_generic_report, frozenset({"1.0.0"}))
