"""Real RSS acquisition. NEXUS Federation F7, mission sections 6, 7, 8, 9.

Uses only Python's standard library (`urllib.request`, `xml.etree.
ElementTree`) -- RSS 2.0 is a small, well-specified XML grammar and does
not require a third-party parser dependency. No API key, no
authentication, no paywall bypass: every configured source is a public
RSS feed reachable with a plain HTTP GET.
"""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

from schema import SourceClass, SourceHealth, SourceHealthStatus, SourceItem

USER_AGENT = "NEXUS-Federation-NewsIntelligence/0.1 (F7 research institution)"


class SourceConfig:
    """One configured, bounded source (mission section 6: 'build a small
    high-quality source set before broad coverage')."""

    def __init__(self, source_id: str, feed_url: str, publisher: str,
                 source_class: SourceClass, language: str, geography: str):
        self.source_id = source_id
        self.feed_url = feed_url
        self.publisher = publisher
        self.source_class = source_class
        self.language = language
        self.geography = geography


# The bounded initial source set (mission section 6). Both are public,
# no-auth RSS feeds, confirmed live (HTTP 200) during F7 construction.
SOURCE_REGISTRY: list[SourceConfig] = [
    SourceConfig(
        source_id="vnexpress_kinh_doanh",
        feed_url="https://vnexpress.net/rss/kinh-doanh.rss",
        publisher="VnExpress",
        source_class=SourceClass.MAINSTREAM_NEWS,
        language="vi",
        geography="Vietnam",
    ),
    SourceConfig(
        source_id="bbc_business",
        feed_url="https://feeds.bbci.co.uk/news/business/rss.xml",
        publisher="BBC News",
        source_class=SourceClass.MAINSTREAM_NEWS,
        language="en",
        geography="UK/International",
    ),
]


def _canonical_url(url: str) -> str:
    """Strip common tracking query params for stable identity. A real,
    minimal normalization -- not a full canonicalization service."""
    return url.split("?")[0].split("#")[0].strip()


def _content_hash(headline: str, canonical_url: str) -> str:
    raw = f"{canonical_url}|{headline.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _source_item_id(canonical_url: str, guid: Optional[str]) -> str:
    """Stable identity per mission section 8: prefer provider GUID when
    present (RSS's own dedup mechanism), fall back to canonical URL."""
    basis = guid or canonical_url
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


def _parse_rss_datetime(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


def fetch_source(config: SourceConfig, timeout: float = 15.0) -> tuple[list[SourceItem], SourceHealth]:
    """Real HTTP GET + real XML parse. Returns (items, health) -- a
    provider outage returns an EMPTY item list and a health record
    marked UNAVAILABLE/DEGRADED, never a synthetic replacement story
    (mission section 7's explicit prohibition)."""

    started = time.monotonic()
    retrieval_ts = datetime.now(timezone.utc).isoformat()

    request = urllib.request.Request(config.feed_url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            http_status = response.status
            raw_bytes = response.read()
        latency = time.monotonic() - started
    except urllib.error.HTTPError as exc:
        return [], SourceHealth(
            source_id=config.source_id, last_success=None,
            latency_seconds=time.monotonic() - started, http_status=exc.code,
            parse_success=False, duplicate_rate=None, item_yield=0,
            rate_limited=(exc.code == 429), auth_required=(exc.code in (401, 403)),
            status=SourceHealthStatus.UNAVAILABLE,
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return [], SourceHealth(
            source_id=config.source_id, last_success=None,
            latency_seconds=time.monotonic() - started, http_status=None,
            parse_success=False, duplicate_rate=None, item_yield=0,
            rate_limited=False, auth_required=False,
            status=SourceHealthStatus.UNAVAILABLE,
        )

    try:
        root = ET.fromstring(raw_bytes)
    except ET.ParseError:
        return [], SourceHealth(
            source_id=config.source_id, last_success=None, latency_seconds=latency,
            http_status=http_status, parse_success=False, duplicate_rate=None,
            item_yield=0, rate_limited=False, auth_required=False,
            status=SourceHealthStatus.DEGRADED,
        )

    items: list[SourceItem] = []
    now = datetime.now(timezone.utc)

    for item_el in root.iter("item"):
        title_el = item_el.find("title")
        link_el = item_el.find("link")
        guid_el = item_el.find("guid")
        pubdate_el = item_el.find("pubDate")
        desc_el = item_el.find("description")

        headline = (title_el.text or "").strip() if title_el is not None else ""
        link = (link_el.text or "").strip() if link_el is not None else ""
        if not headline or not link:
            continue  # malformed item, skipped, not fabricated

        canonical = _canonical_url(link)
        guid = (guid_el.text or "").strip() if guid_el is not None else None
        pub_ts = _parse_rss_datetime(pubdate_el.text if pubdate_el is not None else None)
        description = (desc_el.text or "") if desc_el is not None else ""

        # Future-timestamp guard (mission section 31: "future timestamp").
        if pub_ts:
            try:
                parsed = datetime.fromisoformat(pub_ts)
                if parsed > now:
                    pub_ts = None  # do not trust an impossible future publication time
            except ValueError:
                pub_ts = None

        items.append(SourceItem(
            source_item_id=_source_item_id(canonical, guid),
            canonical_url=canonical,
            publisher=config.publisher,
            source_class=config.source_class,
            author="UNKNOWN",  # RSS 2.0 <author> is rare and unreliable; not fabricated
            publication_timestamp=pub_ts,
            retrieval_timestamp=retrieval_ts,
            content_hash=_content_hash(headline, canonical),
            headline=headline,
            language=config.language,
            geography=config.geography,
            external_identifiers={"rss_guid": guid} if guid else {},
            retrieval_method="RSS",
            license_access_status="PUBLIC_RSS_NO_AUTH",
            verification_status="UNVERIFIED",
            raw_description=description,
        ))

    health = SourceHealth(
        source_id=config.source_id,
        last_success=retrieval_ts if items else None,
        latency_seconds=round(latency, 3),
        http_status=http_status,
        parse_success=True,
        duplicate_rate=None,  # computed at the store layer, across acquisition runs
        item_yield=len(items),
        rate_limited=False,
        auth_required=False,
        status=SourceHealthStatus.AVAILABLE if items else SourceHealthStatus.DEGRADED,
    )

    return items, health
