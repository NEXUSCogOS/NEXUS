"""News Intelligence core schemas. NEXUS Federation F7.

Every enum/dataclass here corresponds directly to a mission requirement
(sections 4, 5, 10-14, 15-19). Nothing here is aspirational -- every
field is populated by real acquisition/extraction code in this package,
never a placeholder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ======================================================================
# Section 4: Source taxonomy
# ======================================================================

class SourceClass(str, Enum):
    PRIMARY_OFFICIAL = "PRIMARY_OFFICIAL"
    GOVERNMENT = "GOVERNMENT"
    REGULATOR = "REGULATOR"
    EXCHANGE = "EXCHANGE"
    COMPANY_PRIMARY = "COMPANY_PRIMARY"
    WIRE_SERVICE = "WIRE_SERVICE"
    MAINSTREAM_NEWS = "MAINSTREAM_NEWS"
    TRADE_PUBLICATION = "TRADE_PUBLICATION"
    SPECIALIST_MEDIA = "SPECIALIST_MEDIA"
    ACADEMIC_OR_RESEARCH = "ACADEMIC_OR_RESEARCH"
    LOCAL_MEDIA = "LOCAL_MEDIA"
    SOCIAL_PRIMARY_ACCOUNT = "SOCIAL_PRIMARY_ACCOUNT"
    SOCIAL_SECONDARY = "SOCIAL_SECONDARY"
    BLOG = "BLOG"
    AGGREGATOR = "AGGREGATOR"
    UNKNOWN = "UNKNOWN"


# Popularity is NEVER used to infer reliability (mission section 4's
# explicit prohibition) -- this table records only each source's OWN
# declared institutional class, a fact about the source, not a ranking.
KNOWN_SOURCE_CLASSES: dict[str, SourceClass] = {
    "vnexpress.net": SourceClass.MAINSTREAM_NEWS,
}


class SourceHealthStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UNVERIFIED = "UNVERIFIED"


@dataclass
class SourceHealth:
    """Mission section 7."""
    source_id: str
    last_success: Optional[str]
    latency_seconds: Optional[float]
    http_status: Optional[int]
    parse_success: bool
    duplicate_rate: Optional[float]
    item_yield: int
    rate_limited: bool
    auth_required: bool
    status: SourceHealthStatus


# ======================================================================
# Section 5: Source provenance (per acquired item)
# ======================================================================

@dataclass
class SourceItem:
    """One acquired, normalized item. Every field mission section 5
    requires; unresolved fields stay the literal string 'UNKNOWN', never
    a fabricated guess."""
    source_item_id: str          # stable identity, see canonical_identity.py
    canonical_url: str
    publisher: str
    source_class: SourceClass
    author: str                  # 'UNKNOWN' if not disclosed by the feed
    publication_timestamp: Optional[str]
    retrieval_timestamp: str
    content_hash: str
    headline: str
    language: str
    geography: str                # 'UNKNOWN' unless inferable
    external_identifiers: dict     # e.g. {'rss_guid': ...}
    retrieval_method: str          # e.g. 'RSS'
    license_access_status: str     # e.g. 'PUBLIC_RSS_NO_AUTH'
    verification_status: str       # 'UNVERIFIED' until independently corroborated
    raw_description: str = ""


# ======================================================================
# Sections 10-11: Entities
# ======================================================================

class EntityResolutionState(str, Enum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"


class EntityType(str, Enum):
    PERSON = "PERSON"
    COMPANY = "COMPANY"
    TICKER = "TICKER"
    GOVERNMENT_BODY = "GOVERNMENT_BODY"
    LOCATION = "LOCATION"
    PROJECT = "PROJECT"
    INDUSTRY = "INDUSTRY"
    COMMODITY = "COMMODITY"
    COUNTRY = "COUNTRY"
    ORGANIZATION = "ORGANIZATION"
    UNKNOWN = "UNKNOWN"


@dataclass
class ExtractedEntity:
    surface_form: str
    entity_type: EntityType
    canonical_entity: Optional[str]   # None if not resolved
    resolution_state: EntityResolutionState
    resolution_basis: str             # always stated, never blank
    resolution_confidence: Optional[float] = None  # None (not a fabricated number) unless a real basis computed one


# ======================================================================
# Section 13: Event taxonomy
# ======================================================================

class EventType(str, Enum):
    REGULATORY = "REGULATORY"
    POLICY = "POLICY"
    CORPORATE = "CORPORATE"
    EARNINGS = "EARNINGS"
    CAPITAL_MARKETS = "CAPITAL_MARKETS"
    M_AND_A = "M_AND_A"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    PLANNING = "PLANNING"
    GEOPOLITICAL = "GEOPOLITICAL"
    MACROECONOMIC = "MACROECONOMIC"
    SUPPLY_CHAIN = "SUPPLY_CHAIN"
    COMMODITY = "COMMODITY"
    TECHNOLOGY = "TECHNOLOGY"
    CYBER = "CYBER"
    LEGAL = "LEGAL"
    ENVIRONMENTAL = "ENVIRONMENTAL"
    EDUCATION = "EDUCATION"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


# ======================================================================
# Section 14: Claim / event epistemology
# ======================================================================

class ClaimEpistemology(str, Enum):
    REPORTED_CLAIM = "REPORTED_CLAIM"
    PRIMARY_SOURCE_FACT = "PRIMARY_SOURCE_FACT"
    MULTI_SOURCE_CORROBORATED_EVENT = "MULTI_SOURCE_CORROBORATED_EVENT"
    UNVERIFIED_REPORT = "UNVERIFIED_REPORT"
    RUMOR = "RUMOR"
    CORRECTION = "CORRECTION"
    RETRACTION = "RETRACTION"
    CONTRADICTORY_REPORTING = "CONTRADICTORY_REPORTING"
    UNKNOWN = "UNKNOWN"


# ======================================================================
# Section 19: Conflict / corroboration state
# ======================================================================

class CorroborationState(str, Enum):
    CORROBORATED = "CORROBORATED"
    PARTIAL = "PARTIAL"
    CONTRADICTORY = "CONTRADICTORY"
    UNVERIFIED = "UNVERIFIED"
    RETRACTED = "RETRACTED"


# ======================================================================
# Section 17: Novelty
# ======================================================================

class NoveltyState(str, Enum):
    NEW = "NEW"
    UPDATE = "UPDATE"
    REPEAT = "REPEAT"
    CORRECTION = "CORRECTION"
    RETRACTION = "RETRACTION"
    ONGOING = "ONGOING"
    UNKNOWN = "UNKNOWN"


# ======================================================================
# Section 12: Event object
# ======================================================================

@dataclass
class Event:
    event_id: str
    event_type: EventType
    headline_summary: str
    entities: list[ExtractedEntity]
    locations: list[str]
    event_time: Optional[str]         # best estimate of when it happened; None if unknown
    publication_time: str
    first_seen: str
    last_seen: str
    source_ids: list[str]
    source_count: int
    independent_source_count: int
    evidence_refs: list[str]
    provenance_refs: list[str]
    novelty: NoveltyState
    materiality: dict                  # {'score': int, 'basis': str} -- see materiality.py
    uncertainty: list[str]
    freshness: str                      # 'CURRENT' | 'STALE' relative to event_time
    status: CorroborationState
    claim_epistemology: ClaimEpistemology
    cluster_id: Optional[str] = None
