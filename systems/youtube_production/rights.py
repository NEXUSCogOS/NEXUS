"""Rights/licensing model. NEXUS Federation F8, mission section 12:
"UNKNOWN rights must not silently become usable."
"""

from __future__ import annotations

from schema import RightsRecord, RightsStatus

_USABLE_STATUSES = frozenset({
    RightsStatus.CLEARED.value,
    RightsStatus.LICENSED.value,
    RightsStatus.OWNED.value,
    RightsStatus.PUBLIC_DOMAIN.value,
    RightsStatus.GENERATED.value,
})


def make_generated_asset_rights(asset_id: str, generator: str, prompt_or_reference: str) -> RightsRecord:
    """Self-generated assets (macOS `say` audio, Pillow-rendered stills)
    are CLEARED-equivalent: this process generated them from evidence
    text/data, no third-party creator, no license to track."""
    return RightsRecord(
        asset_id=asset_id,
        source=f"generated:{generator}",
        license_status=RightsStatus.GENERATED.value,
        creator="nexus_federation_youtube_production (self-generated)",
        retrieval_method="local_generation",
        usage_basis=f"generated internally from evidence-derived text/data via {generator}: {prompt_or_reference!r}",
        modification="none beyond generation itself",
        attribution_required=False,
        rights_status=RightsStatus.GENERATED.value,
        usable=True,
    )


def make_unknown_rights(asset_id: str, source: str) -> RightsRecord:
    """An asset whose rights were never established -- the required
    negative-control shape. usable is always False here; nothing may
    silently flip this to True."""
    return RightsRecord(
        asset_id=asset_id,
        source=source,
        license_status=RightsStatus.UNKNOWN.value,
        creator="UNKNOWN",
        retrieval_method="UNKNOWN",
        usage_basis="UNKNOWN",
        modification="UNKNOWN",
        attribution_required=True,  # fail toward requiring attribution, never assume none needed
        rights_status=RightsStatus.UNKNOWN.value,
        usable=False,
    )


def enforce_rights(records: list[RightsRecord]) -> tuple[list[RightsRecord], list[RightsRecord]]:
    """Returns (usable, blocked). A record's `usable` flag is trusted
    only because it was set exclusively by make_generated_asset_rights
    (True) or is otherwise False by construction -- this function is the
    single gate a render step must call before consuming any asset."""
    usable = [r for r in records if r.rights_status in _USABLE_STATUSES and r.usable]
    blocked = [r for r in records if not (r.rights_status in _USABLE_STATUSES and r.usable)]
    return usable, blocked
