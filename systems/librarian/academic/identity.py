"""Document identity: stable external identifiers preferred, never a
filename.

NEW module, NEXUS Librarian F4.
"""

from __future__ import annotations

import hashlib

_PREFERRED_ID_ORDER = ["doi", "pmid", "pmcid", "arxiv", "isbn", "standards_id", "official_publication_id"]


def compute_source_id(*, external_identifiers: dict[str, str], canonical_url: str | None, fallback_content: str) -> str:
    """Prefer a stable external identifier, in the order DOI > PMID/PMCID
    > arXiv > ISBN > standards ID > official publication ID > canonical
    URL. Only if NONE of those exist does this fall back to a
    content-addressed identifier (sha256 of the retrievable text) --
    never a filename, which is not stable across a re-download or a path
    change."""
    for key in _PREFERRED_ID_ORDER:
        value = external_identifiers.get(key)
        if value:
            return f"{key}:{value}"
    if canonical_url:
        return f"url:{canonical_url}"
    return f"content:{hashlib.sha256(fallback_content.strip().encode('utf-8')).hexdigest()}"
