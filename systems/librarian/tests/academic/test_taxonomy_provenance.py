"""Source taxonomy, evidence weighting, provenance, and identity tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from academic.identity import compute_source_id
from academic.provenance import AcademicProvenance, RetractionStatus, VerificationStatus
from academic.taxonomy import QuestionDomain, SourceType, evidence_weight


def test_domain_neutral_default_prefers_meta_analysis_over_single_study():
    assert evidence_weight(SourceType.META_ANALYSIS) < evidence_weight(SourceType.PEER_REVIEWED_JOURNAL)


def test_software_api_domain_prefers_official_docs_over_journal():
    """Mission example: official documentation may outrank an old journal
    article for software API behavior questions."""
    w_docs = evidence_weight(SourceType.OFFICIAL_TECHNICAL_DOCUMENTATION, domain=QuestionDomain.SOFTWARE_API_BEHAVIOR)
    w_journal = evidence_weight(SourceType.PEER_REVIEWED_JOURNAL, domain=QuestionDomain.SOFTWARE_API_BEHAVIOR)
    assert w_docs < w_journal


def test_current_law_domain_prefers_primary_source_over_commentary():
    w_primary = evidence_weight(SourceType.PRIMARY_SOURCE, domain=QuestionDomain.CURRENT_LAW_OR_REGULATION)
    w_journal = evidence_weight(SourceType.PEER_REVIEWED_JOURNAL, domain=QuestionDomain.CURRENT_LAW_OR_REGULATION)
    assert w_primary < w_journal


def test_scientific_mechanism_domain_prefers_meta_analysis_over_single_study():
    w_meta = evidence_weight(SourceType.META_ANALYSIS, domain=QuestionDomain.SCIENTIFIC_MECHANISM)
    w_primary = evidence_weight(SourceType.PRIMARY_SOURCE, domain=QuestionDomain.SCIENTIFIC_MECHANISM)
    assert w_meta < w_primary


def test_market_fact_domain_prefers_primary_source_over_academic_journal():
    w_primary = evidence_weight(SourceType.PRIMARY_SOURCE, domain=QuestionDomain.MARKET_FACT)
    w_journal = evidence_weight(SourceType.PEER_REVIEWED_JOURNAL, domain=QuestionDomain.MARKET_FACT)
    assert w_primary < w_journal


def test_weight_never_crashes_on_general_domain_unknown_type():
    assert evidence_weight(SourceType.UNKNOWN) > evidence_weight(SourceType.PRIMARY_SOURCE)


# ---- identity --------------------------------------------------------------

def test_doi_preferred_over_arxiv_and_url():
    sid = compute_source_id(
        external_identifiers={"doi": "10.1234/x", "arxiv": "2104.08663"},
        canonical_url="https://arxiv.org/abs/2104.08663",
        fallback_content="text",
    )
    assert sid == "doi:10.1234/x"


def test_arxiv_preferred_over_url_when_no_doi():
    sid = compute_source_id(
        external_identifiers={"arxiv": "2104.08663"}, canonical_url="https://arxiv.org/abs/2104.08663", fallback_content="text"
    )
    assert sid == "arxiv:2104.08663"


def test_content_hash_fallback_when_no_identifiers_at_all():
    sid = compute_source_id(external_identifiers={}, canonical_url=None, fallback_content="unique text body")
    assert sid.startswith("content:")
    assert len(sid.split(":", 1)[1]) == 64  # real sha256 hex digest, not a placeholder


def test_identity_never_uses_a_filename():
    """Structural proof: compute_source_id's signature has no `filename`
    parameter at all -- a filename cannot be passed in even by mistake."""
    import inspect

    sig = inspect.signature(compute_source_id)
    assert "filename" not in sig.parameters


# ---- provenance -------------------------------------------------------------

def test_provenance_requires_at_least_one_identifier():
    with pytest.raises(ValidationError):
        AcademicProvenance(
            source_id="content:abc",
            title="t",
            source_type=SourceType.ACADEMIC_PREPRINT,
            ingestion_method="test",
            verification_status=VerificationStatus.UNVERIFIED,
            doi="UNKNOWN",
            external_identifiers={},
            canonical_url="UNKNOWN",
        )


def test_provenance_unknown_fields_stay_unknown_not_fabricated():
    prov = AcademicProvenance(
        source_id="arxiv:2104.08663",
        title="t",
        source_type=SourceType.ACADEMIC_PREPRINT,
        ingestion_method="test",
        verification_status=VerificationStatus.PARTIAL,
        external_identifiers={"arxiv": "2104.08663"},
    )
    assert prov.doi == "UNKNOWN"
    assert prov.journal_or_venue == "UNKNOWN"
    assert prov.publication_date == "UNKNOWN"


def test_retracted_source_auto_notes_correction_status():
    prov = AcademicProvenance(
        source_id="arxiv:x",
        title="t",
        source_type=SourceType.ACADEMIC_PREPRINT,
        ingestion_method="test",
        verification_status=VerificationStatus.VERIFIED,
        external_identifiers={"arxiv": "x"},
        retraction_status=RetractionStatus.RETRACTED,
    )
    assert prov.correction_status != "NONE"  # a retraction is never silently unremarked
