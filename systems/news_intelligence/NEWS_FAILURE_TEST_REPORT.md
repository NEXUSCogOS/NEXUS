# NEWS FAILURE TEST REPORT
**NEXUS Federation F7 — 2026-08-28**

## Section 31: Source failure tests

| Test | Mechanism | Result |
|---|---|---|
| HTTP/host unavailable | Real request to a deliberately unresolvable hostname | `items=[]`, `health.status=UNAVAILABLE` — PASS |
| Malformed feed | Real local HTTP server returning deliberately truncated/invalid XML | `items=[]`, `health.status=DEGRADED`, `parse_success=False` — PASS |
| Future timestamp | A publication timestamp 10 years in the future | Per-item guard in `fetch_source()` nulls any `pub_ts > now()` before storage, confirmed both by direct `_parse_rss_datetime` inspection and by code review of the guard itself — PASS |
| Duplicate item (same content, re-fetched) | Same live article fetched twice | Second fetch recognized as duplicate via `content_hash` match — no new version stored (see `test_f7_event_idempotency_same_article_replay`) — PASS |
| Missing publication timestamp | RSS `<item>` with no `<pubDate>` element | `SourceItem.publication_timestamp = None` (never fabricated), `Event.event_time` falls back to `None`/`freshness=UNKNOWN` rather than a guessed date — verified by code inspection of `fetch_source()`'s `pubdate_el is not None` guard |
| Ambiguous entity | A ticker-length string matching an unrelated word or URL fragment | Two real defects found and FIXED during construction (not merely tested): "DPR" matching inside an image URL's `&dpr=1&` parameter, and "IDI" matching inside "NVIDIA" — both fixed via HTML/URL stripping + word-boundary regex matching. See NEWS_F7_FORENSIC_REPORT.md and the module docstrings in `entity_resolution.py`/`event_engine.py` for the full account. |

## What was NOT built as a dedicated failure test

- **Article correction / source retraction**: `CorroborationState.RETRACTED` and `NoveltyState.CORRECTION`/`RETRACTION` exist in the schema and the versioning mechanism (`storage.py::store_source_item`, new version on content change) supports representing a correction as a new version — but no real correction/retraction was observed live during this mission's construction to exercise end-to-end, and no synthetic one was fabricated to test it (would violate this mission's own no-fabrication discipline). This is an honest scope gap, not a silently-skipped requirement.
- **Rate limit**: Neither of the two configured sources (VnExpress, BBC) returned a 429 during construction. The acquisition layer's HTTPError handler explicitly classifies `exc.code == 429` as `rate_limited=True` (code-reviewable in `acquisition.py::fetch_source`), but this path was not exercised against a real rate-limited response.

## Contradictory source test

See NEWS_INSTITUTIONAL_CONTRACT.md and `test_f7_contradictory_source_fixture_only`
(mission section 30, fixtures only — not real-world evidence). Proves
`assess_corroboration_state()` returns `CONTRADICTORY` when a
contradiction flag is set, regardless of independent source count, and
never collapses disagreement into `CORROBORATED` merely because 2+
sources exist.
