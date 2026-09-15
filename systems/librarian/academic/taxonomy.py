"""Academic source quality taxonomy and domain-sensitive evidence weighting.

NEW module, NEXUS Librarian F4. A closed classification taxonomy — every
academic source is classified into exactly one of these categories, never
inferred from appearance (a well-formatted PDF is not automatically
PEER_REVIEWED_JOURNAL).

Categories do NOT carry equal evidentiary weight, and the weight itself is
NOT a single fixed ranking — see `evidence_weight()` below: the mission's
own examples (official API docs can outrank an old journal article for
software-behavior questions; primary legislation outranks academic
commentary for current-law questions; a meta-analysis can outrank a
single study for a mechanism question; an authoritative exchange/regulator
can outrank secondary literature for a market fact) are implemented as
explicit, named per-domain override rules — never a blind
"peer-reviewed > everything" assumption.
"""

from __future__ import annotations

from enum import Enum


class SourceType(str, Enum):
    PRIMARY_SOURCE = "PRIMARY_SOURCE"
    PEER_REVIEWED_JOURNAL = "PEER_REVIEWED_JOURNAL"
    PEER_REVIEWED_CONFERENCE = "PEER_REVIEWED_CONFERENCE"
    SYSTEMATIC_REVIEW = "SYSTEMATIC_REVIEW"
    META_ANALYSIS = "META_ANALYSIS"
    ACADEMIC_BOOK = "ACADEMIC_BOOK"
    ACADEMIC_PREPRINT = "ACADEMIC_PREPRINT"
    GOVERNMENT = "GOVERNMENT"
    INTERGOVERNMENTAL = "INTERGOVERNMENTAL"
    STANDARDS_BODY = "STANDARDS_BODY"
    UNIVERSITY = "UNIVERSITY"
    OFFICIAL_TECHNICAL_DOCUMENTATION = "OFFICIAL_TECHNICAL_DOCUMENTATION"
    INDUSTRY_RESEARCH = "INDUSTRY_RESEARCH"
    TECHNICAL_REPORT = "TECHNICAL_REPORT"
    NEWS = "NEWS"
    SECONDARY_WEB = "SECONDARY_WEB"
    INTERNAL_NEXUS_DOCUMENT = "INTERNAL_NEXUS_DOCUMENT"
    UNKNOWN = "UNKNOWN"


# A DEFAULT (domain-neutral) evidentiary rank, highest first. This is the
# fallback ONLY -- `evidence_weight()` below overrides it per question
# domain, per the mission's explicit instruction not to blindly apply
# "peer reviewed > everything" universally.
_DEFAULT_RANK: list[SourceType] = [
    SourceType.PRIMARY_SOURCE,
    SourceType.META_ANALYSIS,
    SourceType.SYSTEMATIC_REVIEW,
    SourceType.PEER_REVIEWED_JOURNAL,
    SourceType.PEER_REVIEWED_CONFERENCE,
    SourceType.ACADEMIC_BOOK,
    SourceType.INTERGOVERNMENTAL,
    SourceType.GOVERNMENT,
    SourceType.STANDARDS_BODY,
    SourceType.OFFICIAL_TECHNICAL_DOCUMENTATION,
    SourceType.UNIVERSITY,
    SourceType.ACADEMIC_PREPRINT,
    SourceType.TECHNICAL_REPORT,
    SourceType.INDUSTRY_RESEARCH,
    SourceType.SECONDARY_WEB,
    SourceType.NEWS,
    SourceType.INTERNAL_NEXUS_DOCUMENT,
    SourceType.UNKNOWN,
]
_DEFAULT_RANK_INDEX = {t: i for i, t in enumerate(_DEFAULT_RANK)}


class QuestionDomain(str, Enum):
    """The domain of the research QUESTION being asked -- not of the
    source. The same source type can rank very differently depending on
    which domain the question falls into (mission section 4)."""

    SOFTWARE_API_BEHAVIOR = "SOFTWARE_API_BEHAVIOR"
    CURRENT_LAW_OR_REGULATION = "CURRENT_LAW_OR_REGULATION"
    SCIENTIFIC_MECHANISM = "SCIENTIFIC_MECHANISM"
    MARKET_FACT = "MARKET_FACT"
    GENERAL = "GENERAL"  # falls back to _DEFAULT_RANK


# Named, explicit per-domain override ranks (highest first). Each entry
# here is a DELIBERATE rationale, recorded in EVIDENCE_HIERARCHY.md, not
# an arbitrary reshuffle.
_DOMAIN_OVERRIDES: dict[QuestionDomain, list[SourceType]] = {
    QuestionDomain.SOFTWARE_API_BEHAVIOR: [
        SourceType.OFFICIAL_TECHNICAL_DOCUMENTATION,  # the vendor's own current docs describe CURRENT behavior
        SourceType.STANDARDS_BODY,
        SourceType.PRIMARY_SOURCE,  # e.g. the actual source code / spec
        SourceType.TECHNICAL_REPORT,
        SourceType.PEER_REVIEWED_CONFERENCE,
        SourceType.PEER_REVIEWED_JOURNAL,  # may describe a now-outdated version
        SourceType.ACADEMIC_PREPRINT,
        SourceType.INDUSTRY_RESEARCH,
        SourceType.UNIVERSITY,
        SourceType.SECONDARY_WEB,
        SourceType.NEWS,
        SourceType.INTERNAL_NEXUS_DOCUMENT,
        SourceType.UNKNOWN,
    ],
    QuestionDomain.CURRENT_LAW_OR_REGULATION: [
        SourceType.PRIMARY_SOURCE,  # the statute/regulation text itself
        SourceType.GOVERNMENT,
        SourceType.INTERGOVERNMENTAL,
        SourceType.STANDARDS_BODY,
        SourceType.PEER_REVIEWED_JOURNAL,  # legal scholarship, secondary to the primary text
        SourceType.ACADEMIC_BOOK,
        SourceType.UNIVERSITY,
        SourceType.TECHNICAL_REPORT,
        SourceType.NEWS,
        SourceType.SECONDARY_WEB,
        SourceType.INTERNAL_NEXUS_DOCUMENT,
        SourceType.UNKNOWN,
    ],
    QuestionDomain.SCIENTIFIC_MECHANISM: [
        SourceType.META_ANALYSIS,  # aggregates many studies, most resistant to single-study noise
        SourceType.SYSTEMATIC_REVIEW,
        SourceType.PEER_REVIEWED_JOURNAL,
        SourceType.PEER_REVIEWED_CONFERENCE,
        SourceType.PRIMARY_SOURCE,  # a single primary study, real but narrower evidentiary scope than a synthesis
        SourceType.ACADEMIC_BOOK,
        SourceType.ACADEMIC_PREPRINT,  # unreviewed
        SourceType.UNIVERSITY,
        SourceType.TECHNICAL_REPORT,
        SourceType.INDUSTRY_RESEARCH,
        SourceType.SECONDARY_WEB,
        SourceType.NEWS,
        SourceType.INTERNAL_NEXUS_DOCUMENT,
        SourceType.UNKNOWN,
    ],
    QuestionDomain.MARKET_FACT: [
        SourceType.PRIMARY_SOURCE,  # the exchange/filing itself
        SourceType.GOVERNMENT,  # the regulator
        SourceType.INTERGOVERNMENTAL,
        SourceType.STANDARDS_BODY,
        SourceType.INDUSTRY_RESEARCH,  # market data providers, close to the fact
        SourceType.TECHNICAL_REPORT,
        SourceType.PEER_REVIEWED_JOURNAL,  # academic finance literature, secondary
        SourceType.PEER_REVIEWED_CONFERENCE,
        SourceType.ACADEMIC_PREPRINT,
        SourceType.UNIVERSITY,
        SourceType.NEWS,
        SourceType.SECONDARY_WEB,
        SourceType.INTERNAL_NEXUS_DOCUMENT,
        SourceType.UNKNOWN,
    ],
}


def evidence_weight(source_type: SourceType, *, domain: QuestionDomain = QuestionDomain.GENERAL) -> int:
    """Lower number = higher evidentiary weight. Domain-sensitive: the
    SAME source_type can have a different rank depending on the question
    domain (see EVIDENCE_HIERARCHY.md for the rationale behind every
    override table above)."""
    ranking = _DOMAIN_OVERRIDES.get(domain, _DEFAULT_RANK)
    try:
        return ranking.index(source_type)
    except ValueError:
        return len(ranking)  # not in this domain's table -> lowest weight, never crashes
