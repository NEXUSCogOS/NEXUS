"""Event construction: type classification, clustering, source
independence, novelty, materiality, epistemology.
NEXUS Federation F7, mission sections 9, 13-19.

Every function here is a fixed, named rule set -- no learned/opaque
scoring anywhere (mission sections 18, 24's shared discipline).
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from schema import (
    ClaimEpistemology,
    CorroborationState,
    Event,
    EventType,
    ExtractedEntity,
    NoveltyState,
)

FRESHNESS_THRESHOLD_DAYS = 2

# ---------------------------------------------------------------------
# Section 13: deterministic event-type classification
# ---------------------------------------------------------------------

_EVENT_TYPE_KEYWORDS: dict[EventType, list[str]] = {
    EventType.EARNINGS: ["earnings", "lợi nhuận", "doanh thu quý", "báo cáo tài chính"],
    EventType.M_AND_A: ["acquisition", "acquire", "merger", "sáp nhập", "mua lại"],
    EventType.REGULATORY: ["regulator", "quy định", "thông tư", "nghị định"],
    EventType.POLICY: ["policy", "chính sách", "chính phủ", "đề xuất"],
    EventType.INFRASTRUCTURE: ["infrastructure", "hạ tầng", "sân bay", "airport", "cảng"],
    EventType.PLANNING: ["quy hoạch", "zoning", "land use", "planning"],
    EventType.CAPITAL_MARKETS: ["market cap", "vốn hóa", "cổ phiếu", "stock", "shares"],
    EventType.SUPPLY_CHAIN: ["supply chain", "chuỗi cung ứng", "xuất khẩu", "export"],
    EventType.COMMODITY: ["oil", "dầu", "opec", "commodity", "giá vàng"],
    EventType.TECHNOLOGY: ["trí tuệ nhân tạo", "công nghệ", "r&d", "chip", "technology"],
    EventType.CORPORATE: ["corporation", "company", "công ty", "doanh nghiệp", "tập đoàn"],
    EventType.MACROECONOMIC: ["gdp", "inflation", "lạm phát", "macro", "kinh tế vĩ mô"],
    EventType.GEOPOLITICAL: ["trump", "geopolit", "chiến sự", "war", "sanction"],
}


def classify_event_type(text: str) -> tuple[EventType, str]:
    """Returns (type, basis). First matching category in dict-definition
    order wins -- deterministic, not a scored ensemble. UNKNOWN if no
    keyword matches (never forced into an inappropriate category, per
    mission section 13).

    Word-boundary matching (\\b), not raw substring `in`: a real defect
    found during F7 construction had the bare keyword 'ai ' (intended to
    catch the English acronym 'AI') match inside the unrelated Vietnamese
    phrase 'sầu gai đen' ('...gai đen...' contains the literal substring
    'ai '), misclassifying a durian-price article as TECHNOLOGY. Fixed by
    (a) replacing the fragile bare 'ai' keyword with the distinctive
    Vietnamese compound term 'trí tuệ nhân tạo' ('artificial
    intelligence'), and (b) requiring \\b-bounded matches for every
    keyword, English and Vietnamese alike."""
    lowered = text.lower()
    for event_type, keywords in _EVENT_TYPE_KEYWORDS.items():
        matched = [
            k for k in keywords
            if re.search(r"\b" + re.escape(k.strip()) + r"\b", lowered)
        ]
        if matched:
            return event_type, f"keyword match: {matched}"
    return EventType.UNKNOWN, "no configured keyword matched"


# ---------------------------------------------------------------------
# Section 9/16: clustering (syndication + same-underlying-event grouping)
# ---------------------------------------------------------------------

def cluster_items_by_identity(items: list) -> dict[str, list]:
    """Exact/near-duplicate clustering by content_hash (mission section
    9). Two items with the SAME content_hash are the same underlying
    content -- one event family, source count preserved."""
    clusters: dict[str, list] = {}
    for item in items:
        clusters.setdefault(item.content_hash, []).append(item)
    return clusters


def cluster_key_for_event(entities: list[ExtractedEntity], event_type: EventType) -> str:
    """A coarser clustering key for grouping DIFFERENT articles about the
    SAME underlying event (mission section 16): resolved canonical
    entities + event type. Deliberately does NOT use headline text
    (would overmerge on shared generic words) and does NOT use company
    alone (mission's explicit "do not overmerge... simply because they
    share a company" warning) -- entity SET + event type together."""
    canonical_entities = sorted(
        e.canonical_entity for e in entities
        if e.canonical_entity is not None
    )
    basis = f"{event_type.value}|{'|'.join(canonical_entities)}"
    return hashlib.sha256(basis.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------
# Section 15: source independence
# ---------------------------------------------------------------------

def assess_source_independence(items: list) -> tuple[int, str]:
    """Distinct PUBLISHERS within one content-hash cluster = independent
    lineages. N copies of one wire story from the same publisher (or
    re-fetched across acquisition runs) count as ONE independent source,
    not N (mission section 15's explicit example)."""
    distinct_publishers = {item.publisher for item in items}
    return len(distinct_publishers), (
        f"{len(distinct_publishers)} distinct publisher(s) "
        f"({sorted(distinct_publishers)}) across {len(items)} item(s) "
        f"sharing identical content_hash"
    )


# ---------------------------------------------------------------------
# Section 14: claim epistemology
# ---------------------------------------------------------------------

def determine_claim_epistemology(
    source_class_list: list, independent_source_count: int
) -> ClaimEpistemology:
    """A news article is REPORTED_CLAIM by default -- never
    auto-promoted to PRIMARY_SOURCE_FACT merely because it's from a
    mainstream outlet (mission section 14's explicit warning). Only a
    PRIMARY_OFFICIAL/GOVERNMENT/REGULATOR/EXCHANGE/COMPANY_PRIMARY source
    class earns PRIMARY_SOURCE_FACT. Multiple INDEPENDENT (not merely
    syndicated) sources earn MULTI_SOURCE_CORROBORATED_EVENT."""
    from schema import SourceClass

    primary_classes = {
        SourceClass.PRIMARY_OFFICIAL, SourceClass.GOVERNMENT,
        SourceClass.REGULATOR, SourceClass.EXCHANGE, SourceClass.COMPANY_PRIMARY,
    }
    if any(sc in primary_classes for sc in source_class_list):
        return ClaimEpistemology.PRIMARY_SOURCE_FACT
    if independent_source_count >= 2:
        return ClaimEpistemology.MULTI_SOURCE_CORROBORATED_EVENT
    return ClaimEpistemology.REPORTED_CLAIM


# ---------------------------------------------------------------------
# Section 17: novelty
# ---------------------------------------------------------------------

def assess_novelty(cluster_key: str, existing_events: list[dict]) -> tuple[NoveltyState, str]:
    """Compares against STORED prior events (mission section 17) -- a
    freshly-fetched article about an event already in the store is UPDATE
    or REPEAT, never re-classified as NEW merely because it was fetched
    today."""
    matches = [e for e in existing_events if e.get("cluster_id") == cluster_key]
    if not matches:
        return NoveltyState.NEW, "no prior event found with this cluster_id"
    return NoveltyState.UPDATE, f"{len(matches)} prior event version(s) found with this cluster_id"


# ---------------------------------------------------------------------
# Section 18: materiality (deterministic, disclosed factors)
# ---------------------------------------------------------------------

def assess_materiality(
    *,
    source_class_list: list,
    event_type: EventType,
    independent_source_count: int,
    resolved_entity_count: int,
    unresolved_entity_count: int,
    geography: str,
    novelty: NoveltyState,
) -> dict:
    from schema import SourceClass

    score = 0
    reasons = []

    primary_classes = {SourceClass.PRIMARY_OFFICIAL, SourceClass.GOVERNMENT, SourceClass.REGULATOR}
    source_quality = 2 if any(sc in primary_classes for sc in source_class_list) else 1
    score += source_quality
    reasons.append(f"source_quality={source_quality}")

    high_materiality_types = {
        EventType.REGULATORY, EventType.M_AND_A, EventType.INFRASTRUCTURE,
        EventType.PLANNING, EventType.MACROECONOMIC,
    }
    type_score = 2 if event_type in high_materiality_types else (1 if event_type != EventType.UNKNOWN else 0)
    score += type_score
    reasons.append(f"event_type_score={type_score}({event_type.value})")

    entity_score = min(2, resolved_entity_count)
    score += entity_score
    reasons.append(f"resolved_entity_score={entity_score}")

    geo_score = 1 if geography not in ("UNKNOWN", "") else 0
    score += geo_score
    reasons.append(f"geographic_scope_score={geo_score}")

    corroboration_score = min(2, independent_source_count)
    score += corroboration_score
    reasons.append(f"independent_corroboration_score={corroboration_score}")

    novelty_score = 1 if novelty == NoveltyState.NEW else 0
    score += novelty_score
    reasons.append(f"novelty_score={novelty_score}")

    unresolved_penalty = -min(2, unresolved_entity_count)
    score += unresolved_penalty
    reasons.append(f"unresolved_entity_penalty={unresolved_penalty}")

    return {
        "score": score,
        "basis": " + ".join(reasons) + f" = {score}",
    }


# ---------------------------------------------------------------------
# Section 20: temporal / freshness
# ---------------------------------------------------------------------

def assess_freshness(event_time: Optional[str], now: Optional[datetime] = None) -> str:
    now = now or datetime.now(timezone.utc)
    if not event_time:
        return "UNKNOWN"
    try:
        parsed = datetime.fromisoformat(event_time)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age_days = (now - parsed).days
        return "CURRENT" if age_days <= FRESHNESS_THRESHOLD_DAYS else "STALE"
    except ValueError:
        return "UNKNOWN"


# ---------------------------------------------------------------------
# Section 19: corroboration / conflict state
# ---------------------------------------------------------------------

def assess_corroboration_state(
    independent_source_count: int, has_contradiction: bool
) -> CorroborationState:
    if has_contradiction:
        return CorroborationState.CONTRADICTORY
    if independent_source_count >= 2:
        return CorroborationState.CORROBORATED
    if independent_source_count == 1:
        return CorroborationState.PARTIAL
    return CorroborationState.UNVERIFIED


def build_event(
    *,
    items: list,
    entities: list[ExtractedEntity],
    existing_events: list[dict],
    has_contradiction: bool = False,
) -> Event:
    """Assembles a real Event from a cluster of acquired items + resolved
    entities. This is the one function that ties every prior section
    together."""

    now = datetime.now(timezone.utc)
    from entity_resolution import clean_text_for_extraction
    combined_text = " ".join(
        i.headline + " " + clean_text_for_extraction(i.raw_description) for i in items
    )
    event_type, type_basis = classify_event_type(combined_text)

    cluster_key = cluster_key_for_event(entities, event_type)
    novelty, novelty_basis = assess_novelty(cluster_key, existing_events)

    independent_count, independence_basis = assess_source_independence(items)
    source_classes = [i.source_class for i in items]
    epistemology = determine_claim_epistemology(source_classes, independent_count)

    resolved = [e for e in entities if e.canonical_entity is not None]
    unresolved = [e for e in entities if e.canonical_entity is None]
    locations = [e.canonical_entity for e in entities if e.entity_type.value == "LOCATION" and e.canonical_entity]

    pub_times = [i.publication_timestamp for i in items if i.publication_timestamp]
    event_time = min(pub_times) if pub_times else None
    freshness = assess_freshness(event_time, now)

    materiality = assess_materiality(
        source_class_list=source_classes,
        event_type=event_type,
        independent_source_count=independent_count,
        resolved_entity_count=len(resolved),
        unresolved_entity_count=len(unresolved),
        geography=items[0].geography if items else "UNKNOWN",
        novelty=novelty,
    )

    status = assess_corroboration_state(independent_count, has_contradiction)

    uncertainty = []
    if unresolved:
        uncertainty.append(
            f"{len(unresolved)} entity mention(s) could not be resolved to a canonical entity: "
            f"{[e.surface_form for e in unresolved]}"
        )
    uncertainty.append(f"event_type basis: {type_basis}")
    uncertainty.append(f"novelty basis: {novelty_basis}")
    uncertainty.append(f"source_independence basis: {independence_basis}")

    return Event(
        event_id=str(uuid4()),
        event_type=event_type,
        headline_summary=items[0].headline if items else "UNKNOWN",
        entities=entities,
        locations=locations,
        event_time=event_time,
        publication_time=items[0].publication_timestamp or now.isoformat(),
        first_seen=now.isoformat(),
        last_seen=now.isoformat(),
        source_ids=[i.source_item_id for i in items],
        source_count=len(items),
        independent_source_count=independent_count,
        evidence_refs=[f"source_item:{i.source_item_id}" for i in items],
        provenance_refs=[f"content_hash:{i.content_hash}" for i in items],
        novelty=novelty,
        materiality=materiality,
        uncertainty=uncertainty,
        freshness=freshness,
        status=status,
        claim_epistemology=epistemology,
        cluster_id=cluster_key,
    )
