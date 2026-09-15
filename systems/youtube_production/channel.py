"""Channel selection against the REAL, already-existing channel identities
defined in the pre-existing YouTube estate. NEXUS Federation F8, mission
section 18: "Select the channel using explicit editorial relevance
against an ALREADY-EXISTING channel identity... Do not invent a new
channel merely for F8. If none matches: classify NO_APPROPRIATE_CHANNEL."

Per YOUTUBE_F8_FORENSIC_REPORT.md, the 4 formal `channel_manifest.yaml`
files are all `UNASSIGNED`/not build-authorised -- there is no connected,
live external YouTube channel anywhere in this estate. The richer
`channels/channels_config.json`, however, defines three REAL, detailed,
already-designed editorial identities (niche, tone, geography, seed
keywords) that a prior operator built. Selecting one of these for
editorial routing purposes is choosing an existing identity, not inventing a
new one -- but it is explicitly NOT the same as having a live channel to
publish to, and this module never claims otherwise.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

CHANNELS_CONFIG_PATH = Path("/Volumes/NEXUS/NEXUS_LOCAL/systems/youtube/channels/channels_config.json")


def load_existing_channel_identities() -> list[dict]:
    """Real read of the pre-existing config. Returns [] (not a fabricated
    fallback list) if the external volume/file is unavailable."""
    try:
        raw = json.loads(CHANNELS_CONFIG_PATH.read_text())
    except Exception:
        return []
    # channels_config.json's real top-level shape is {channel_key: {...}, ...}
    channels = []
    for key, cfg in raw.items():
        if isinstance(cfg, dict):
            entry = dict(cfg)
            entry.setdefault("channel_key", key)
            channels.append(entry)
    return channels


def select_channel(editorial_objective: str, event_keywords: list[str]) -> tuple[Optional[str], str]:
    """Returns (channel_id or None, reason). Matches the editorial
    objective + event keywords against each existing channel identity's
    own declared niche/seed_keywords -- a real, disclosed rule, never an
    opaque score. No live external youtube_channel_id is asserted; this
    only selects which pre-existing EDITORIAL IDENTITY this production is
    for."""
    channels = load_existing_channel_identities()
    if not channels:
        return None, "channels_config.json unavailable (external volume not mounted or file missing) -- NO_APPROPRIATE_CHANNEL"

    haystack = (editorial_objective + " " + " ".join(event_keywords)).lower()
    best_key = None
    best_score = 0
    best_reason = ""
    for ch in channels:
        seeds = [s.lower() for s in ch.get("seed_keywords", [])]
        niche = str(ch.get("niche", "")).lower()
        score = sum(1 for s in seeds if s in haystack)
        if niche and niche in haystack:
            score += 1
        if score > best_score:
            best_score = score
            best_key = ch.get("channel_key")
            best_reason = f"matched niche={niche!r} / {score} seed keyword(s) against editorial_objective+event_keywords"

    if best_key is None or best_score == 0:
        return None, (
            "no configured channel identity's niche/seed_keywords matched this "
            "editorial objective -- NO_APPROPRIATE_CHANNEL (not forced to a "
            "mismatched channel merely because channels exist)"
        )
    return best_key, best_reason
