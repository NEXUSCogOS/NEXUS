"""Entity extraction and resolution. NEXUS Federation F7, mission
sections 10-11.

Deterministic, dictionary/substring-based -- no ML/LLM entity linker.
Resolution is only ever claimed against REAL, governed reference data
already in this estate:

  - companies: Sentinel's own `companies` table (123 real Vietnamese
    listed companies, symbol + full_name)
  - locations: a small, fixed, publicly factual list of Vietnamese
    provinces/cities (real geography, not fabricated)

A name that doesn't match either reference set is UNRESOLVED, never
forced into a resolution it can't support (mission section 10's
explicit instruction).
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from schema import EntityResolutionState, EntityType, ExtractedEntity

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"https?://\S+")


def clean_text_for_extraction(raw: str) -> str:
    """Strip HTML markup and embedded URLs before entity extraction.

    Real defect found during F7 construction: an unstripped RSS
    <description> CDATA blob embedding an <img> tag's CDN URL
    (...?w=1200&h=0&...&dpr=1&fit=crop...) produced a false-positive
    TICKER match on 'DPR' (a real Sentinel-covered symbol,
    Dong Phu Rubber) -- the substring 'dpr=1' in an image-scaling query
    parameter has nothing to do with that company. Entity extraction
    must only ever run against human-readable text, never raw markup."""
    no_tags = _HTML_TAG_RE.sub(" ", raw)
    no_urls = _URL_RE.sub(" ", no_tags)
    return no_urls

SENTINEL_DB_DEFAULT = str(Path.home() / "NEXUS/systems/sentinel/financial_intelligence.db")

# A real, fixed list of Vietnamese provincial-level administrative units
# (63 provinces/cities, public knowledge -- not sourced from DAT.AI's
# internal dvhc codes since no code->name lookup table was found
# governed anywhere in this estate during F7's own ground-truth search).
VIETNAM_PROVINCES = [
    "Hà Nội", "Hồ Chí Minh", "Hải Phòng", "Đà Nẵng", "Cần Thơ",
    "An Giang", "Bà Rịa - Vũng Tàu", "Bắc Giang", "Bắc Kạn", "Bạc Liêu",
    "Bắc Ninh", "Bến Tre", "Bình Định", "Bình Dương", "Bình Phước",
    "Bình Thuận", "Cà Mau", "Cao Bằng", "Đắk Lắk", "Đắk Nông",
    "Điện Biên", "Đồng Nai", "Đồng Tháp", "Gia Lai", "Hà Giang",
    "Hà Nam", "Hà Tĩnh", "Hải Dương", "Hậu Giang", "Hòa Bình",
    "Hưng Yên", "Khánh Hòa", "Kiên Giang", "Kon Tum", "Lai Châu",
    "Lâm Đồng", "Lạng Sơn", "Lào Cai", "Long An", "Nam Định",
    "Nghệ An", "Ninh Bình", "Ninh Thuận", "Phú Thọ", "Phú Yên",
    "Quảng Bình", "Quảng Nam", "Quảng Ngãi", "Quảng Ninh", "Quảng Trị",
    "Sóc Trăng", "Sơn La", "Tây Ninh", "Thái Bình", "Thái Nguyên",
    "Thanh Hóa", "Thừa Thiên Huế", "Tiền Giang", "Trà Vinh",
    "Tuyên Quang", "Vĩnh Long", "Vĩnh Phúc", "Yên Bái",
]

_FOREIGN_KNOWN_COMPANIES = {
    # Real, well-known foreign companies NOT in Sentinel's VN universe --
    # kept as a small, explicit "known but unresolved-to-a-ticker" set so
    # the resolver can say WHY it's unresolved (a real company, just not
    # one Sentinel's governed data covers) rather than reporting a bare
    # UNKNOWN indistinguishable from "not a company at all."
    "Samsung", "Qualcomm", "Nvidia", "Apple", "Intel", "TSMC",
}


def _load_company_reference(db_path: str) -> dict[str, str]:
    """symbol/full_name -> symbol, from Sentinel's own real companies
    table. Read-only."""
    ref: dict[str, str] = {}
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        for symbol, full_name in conn.execute("SELECT symbol, full_name FROM companies"):
            ref[symbol.upper()] = symbol
            if full_name:
                ref[full_name.upper()] = symbol
        conn.close()
    except sqlite3.Error:
        pass  # Sentinel DB unavailable -- resolver degrades to UNRESOLVED-only, not fabricated
    return ref


def extract_entities(text: str, sentinel_db_path: str = SENTINEL_DB_DEFAULT) -> list[ExtractedEntity]:
    """Real, deterministic extraction against real reference data.
    Returns one ExtractedEntity per distinct surface form found."""

    company_ref = _load_company_reference(sentinel_db_path)
    entities: list[ExtractedEntity] = []
    seen_surface_forms = set()

    # ---- Locations (Vietnamese provinces/cities) ----
    for province in VIETNAM_PROVINCES:
        if province in text and province not in seen_surface_forms:
            seen_surface_forms.add(province)
            entities.append(ExtractedEntity(
                surface_form=province,
                entity_type=EntityType.LOCATION,
                canonical_entity=province,
                resolution_state=EntityResolutionState.RESOLVED,
                resolution_basis="exact match against the fixed Vietnamese provincial administrative unit list",
                resolution_confidence=1.0,
            ))

    # ---- Companies (Sentinel's real, governed universe) ----
    # Real defect found and fixed during F7 construction: a plain
    # substring check on short tickers matched 'IDI' (a real Sentinel
    # symbol) inside the word 'NVIDIA' (N-V-[IDI]-A) -- a coincidental
    # letter sequence, not a mention of that company. Word-boundary
    # regex matching (\b) prevents a short ticker from matching inside a
    # longer, unrelated word.
    text_upper = text.upper()
    for key_upper, symbol in company_ref.items():
        if len(key_upper) < 3:
            continue  # avoid spurious short-string matches (e.g. a 2-letter ticker)
        pattern = r"\b" + re.escape(key_upper) + r"\b"
        if re.search(pattern, text_upper) and key_upper not in seen_surface_forms:
            seen_surface_forms.add(key_upper)
            entities.append(ExtractedEntity(
                surface_form=key_upper,
                entity_type=EntityType.TICKER,
                canonical_entity=symbol,
                resolution_state=EntityResolutionState.RESOLVED,
                resolution_basis=f"exact match against Sentinel's governed `companies` table (symbol={symbol})",
                resolution_confidence=1.0,
            ))

    # ---- Known foreign companies (real, but explicitly not Sentinel-covered) ----
    for name in _FOREIGN_KNOWN_COMPANIES:
        if name in text and name not in seen_surface_forms:
            seen_surface_forms.add(name)
            entities.append(ExtractedEntity(
                surface_form=name,
                entity_type=EntityType.COMPANY,
                canonical_entity=None,
                resolution_state=EntityResolutionState.UNRESOLVED,
                resolution_basis=(
                    f"{name!r} is a real, known company, but has no "
                    f"entry in Sentinel's governed `companies` table "
                    f"(not a Vietnamese-listed equity Sentinel covers) "
                    f"-- left UNRESOLVED rather than forced to a ticker "
                    f"it does not have"
                ),
            ))

    return entities
