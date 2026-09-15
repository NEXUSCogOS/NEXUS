# YOUTUBE RIGHTS MODEL
**NEXUS Federation F8 — 2026-08-28**

Mission section 12: "UNKNOWN rights must not silently become usable."
Implemented in `rights.py` and `schema.py::RightsRecord`.

## Rights status vocabulary

`CLEARED`, `LICENSED`, `OWNED`, `PUBLIC_DOMAIN`, `GENERATED`,
`FAIR_USE_REVIEW_REQUIRED`, `UNKNOWN`, `REJECTED`.

## RightsRecord fields

`asset_id`, `source`, `license_status`, `creator`, `retrieval_method`,
`usage_basis`, `modification`, `attribution_required`, `rights_status`,
`usable` (a derived, never-hand-set-True-by-default boolean).

## The two construction paths

- `rights.make_generated_asset_rights(asset_id, generator, prompt_or_reference)`
  -- for assets THIS package generates itself (macOS `say` narration
  audio, Pillow-rendered stills/thumbnails). These are `GENERATED`,
  `usable=True`, because there is no third-party creator or license to
  track: the process generated them from evidence-derived text, and
  `attribution_required=False`.
- `rights.make_unknown_rights(asset_id, source)` -- for any asset whose
  rights were never established (e.g. a hypothetical third-party stock
  library asset). Always `rights_status=UNKNOWN`, always `usable=False`,
  and `attribution_required=True` by default (fails toward requiring
  attribution, never assumes none is needed).

## Enforcement

`rights.enforce_rights(records)` is the single gate any render step must
call before consuming an asset list. It returns `(usable, blocked)`;
`usable` only ever contains records whose `rights_status` is in the
allow-set (`CLEARED`/`LICENSED`/`OWNED`/`PUBLIC_DOMAIN`/`GENERATED`) AND
whose `usable` flag is `True` -- a record cannot silently flip into the
usable set by any other path. Proven directly by
`test_f8_missing_rights_negative_control`
(`tests/f8/_subprocess_helpers/process_missing_rights_check.py`): an
`UNKNOWN`-status asset is confirmed excluded from the usable set on
every run.

## This mission's real render never touches third-party media at all

The real render path (`media.py`) uses only self-generated assets (local
TTS narration, a Pillow-rendered still) -- there is no stock footage,
stock photo, or scraped media of any kind in this mission's production
path, so there is no third-party rights risk in the real pipeline today.
The `UNKNOWN`-rights negative control exists to prove the GATE works
correctly for the day a future mission does introduce third-party media,
not because this mission's own real render was ever at risk.
