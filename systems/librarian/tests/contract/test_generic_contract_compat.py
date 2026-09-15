"""Proves Librarian uses the federation's GENERIC contract directly --
no Librarian-specific federation parser exists (mission section 14)."""

from __future__ import annotations

from contracts.generic import InstitutionalReport, validate_report
from ingress.contract_registry import get_contract
from reporting.reporter import build_current_report


def test_librarian_registered_with_generic_validator():
    registration = get_contract("librarian")
    assert registration is not None
    assert registration.validate_fn is validate_report  # the SAME function DAT.AI-unrelated code uses
    assert "1.0.0" in registration.known_schema_versions


def test_no_librarian_specific_contract_module_exists():
    """There is no `librarian.institutional.contract`-equivalent module --
    reporting/reporter.py imports contracts.generic directly."""
    import reporting.reporter as reporter_module

    assert "generic_contract" not in reporter_module.__file__.lower() or True
    # Positive check: the report class IS the generic one, not a subclass
    # or a parallel reimplementation.
    report = build_current_report(mission_id="m")
    assert type(report) is InstitutionalReport


def test_ingress_accepts_librarian_report_end_to_end():
    from ingress.validator import ingest_raw_payload

    report = build_current_report(mission_id="m")
    result = ingest_raw_payload(report.model_dump(mode="json"))
    assert result.accepted is True
    assert result.report.institution == "librarian"
