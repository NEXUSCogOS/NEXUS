# FEDERATION F7 IMPLEMENTATION REPORT
**NEXUS Federation F7 — 2026-08-28**

## What was built

A real News/Media Intelligence institution (`systems/news_intelligence/`)
and event-driven routing extension to NEXUS
(`relevance/news_event_router.py`), following ground-truth confirmation
(NEWS_F7_FORENSIC_REPORT.md) that no working news-acquisition capability
existed anywhere in this estate before this mission.

**Modules:** `schema.py` (all typed enums/dataclasses), `acquisition.py`
(real RSS fetch via Python stdlib XML, no third-party dependency),
`entity_resolution.py` (deterministic, dictionary-based, against real
Sentinel company data + a fixed VN province list), `event_engine.py`
(type classification, clustering, source independence, novelty,
materiality, epistemology — all fixed rule sets), `storage.py` (SQLite,
external-first, versioned not overwritten), `institutional_report.py`
(generic-contract report builder).

**Federation registration:** `news_intelligence` added to
`ingress/contract_registry.py` and `kernel.py::INSTITUTION_TYPES`
(`external_world_intelligence`) — same pattern as Sentinel (F5) and the
generic contract Librarian (F3) established; no News-specific parser.

**Test harness:** `tests/f7/`, 8 tests, all passing against LIVE data
(real HTTP calls to VnExpress and BBC on every run, not fixtures) —
full event-driven loop, negative control, contradiction (fixtures only,
per the mission's own instruction), event idempotency, recovery, and
three source-failure modes.

## Three real defects found and fixed during construction

1. **HTML/URL contamination of entity extraction.** An unstripped RSS
   `<description>` CDATA blob containing an `<img>` tag's CDN URL
   (`...&dpr=1&fit=crop...`) produced a false-positive `TICKER` match on
   `DPR` (a real Sentinel symbol, unrelated to the article). Fixed by
   stripping HTML tags and URLs before extraction
   (`entity_resolution.py::clean_text_for_extraction`).

2. **Substring-inside-word false positives.** The ticker `IDI` matched
   inside the unrelated word `NVIDIA` (N-V-**IDI**-A). Fixed with
   word-boundary (`\b`) regex matching instead of plain substring `in`
   checks, for both entity resolution and event-type keyword
   classification.

3. **A fragile keyword classifier.** The bare keyword `"ai "` (meant to
   catch the English acronym "AI") matched inside the unrelated
   Vietnamese phrase "sầu **gai đen**" (a durian variety name),
   misclassifying a durian-pricing article as `TECHNOLOGY`. Fixed by
   replacing it with the distinctive Vietnamese compound term "trí tuệ
   nhân tạo" and applying the same word-boundary discipline.

## A real architectural gap found and fixed, carried over from F6

F6's `synthesize()` (`synthesis/cross_domain_synthesis.py`) implicitly
assumed both Librarian and Sentinel were always delegated to — any
`None` report forced `partial=True`. F7's routing is more flexible
(zero, one, or two of three institutions may be relevant per event),
and reusing `synthesize()` unmodified incorrectly forced a real
single-institution routing outcome (Sentinel relevant, Librarian
correctly never delegated to) into a spurious `partial=True`/
`INSUFFICIENT_EVIDENCE` result. Fixed additively: a new
`expected_institutions` parameter (defaulting to `["librarian",
"sentinel"]`, preserving F6's own behavior unchanged) lets a caller
state which institutions were actually delegated to, so "never
relevant" is no longer conflated with "relevant but failed to respond."

## The real result

**Event:** real VnExpress article, Samsung's $500B cumulative phone
exports from Bắc Ninh/Thái Nguyên facilities. **Routing:** Sentinel only
(materiality 6, `SUPPLY_CHAIN` event type). **Executive conclusion:**
`NO_MATERIAL_CROSS_DOMAIN_EFFECT_ESTABLISHED` — Sentinel's real entity
mapping found no ticker reaching `DIRECT` classification (sector data
only, no facility-level geography). A genuine, bounded, non-inflated
result. Full evidence: NEWS_NEXUS_E2E_EVIDENCE.md.

## Observability (mission section 32)

Measured directly in the real captured run (`process_news_acquire_and_report.py`'s
own output, not estimated):

| Metric | Value (real run) |
|---|---|
| items_fetched | 115 (60 VnExpress + 55 BBC) |
| items_accepted | 115 (first run) |
| duplicates | 0 (first run) / matches prior version on replay |
| events_created | 1 per targeted run (this mission builds one event per acquisition cycle from the highest-signal item, by design — see scope note below) |
| source_failures | 0 (both configured sources AVAILABLE) |
| routing_actions | 1 (Sentinel) |
| no_action_events | 1 (negative control) |

No arbitrary "news intelligence accuracy" percentage is computed or
reported, per the mission's explicit prohibition.

**Scope note:** this mission's acquisition process builds ONE event per
run (from a filterable/highest-materiality target item), not a
full-batch "construct an event for every one of 115 fetched items"
pipeline — a deliberate scope decision to keep the defining experiment
traceable end-to-end, not a limitation of the underlying event-
construction code (which operates on an arbitrary item list already).

## Monitoring loop (mission section 33)

**Designed, not activated.** A LaunchAgent-style scheduled acquisition
job was deliberately NOT installed as a live, running background
process during this mission — installing a new always-on recurring job
against an external website is a durable system change beyond what this
mission's bounded commissioning requires, and mission section 33 itself
says "start conservatively." The bounded design (2 sources, no
authentication, real backoff via `acquisition.py`'s existing exception
handling, idempotent per-item storage) is ready to be scheduled on
request.

## Scientific evaluation (mission section 34)

| Criterion | Verdict |
|---|---|
| Source authenticity | PASS — real, live, public RSS, no fabrication |
| Provenance completeness | PASS — every item carries a real `source_item_id`/`content_hash`/`retrieval_timestamp` |
| Deduplication | PASS — content-hash-based, versioned not overwritten |
| Entity resolution | PASS, with disclosed limitation — only resolves against Sentinel's real companies + a fixed VN province list; foreign companies (Samsung, Qualcomm, Nvidia) correctly UNRESOLVED, not forced |
| Event extraction fidelity | PASS, with two found-and-fixed false-positive classes (see above) |
| Temporal fidelity | PASS — future timestamps nulled, freshness computed relative to real event_time |
| Source independence | PASS (mechanism proven), but this mission's 2-source set rarely produces multi-publisher syndication clusters to exercise it richly |
| Novelty classification | PASS — compares against stored prior events, not "fetched today = new" |
| Materiality reasoning | PASS — fully disclosed, uncalibrated fixed rules (see NEWS_MATERIALITY_MODEL.md) |
| Routing correctness | PASS — verified negative (durian) and positive (Samsung→Sentinel) outcomes |
| Unsupported claim count | 0 — every finding traces to a real evidence_ref |
| Reproducibility | PASS with a caveat — depends on live feed content at run time; the SPECIFIC real article used for this report's evidence will eventually age out of the live feed, but the mechanism itself is fully reproducible against whatever is live at any future run |

No single composite "intelligence score," per the mission's explicit
instruction.

## Regression

NEXUS federation: 145 passed / 1 skipped (pre-existing, unrelated).
Librarian: 114 passed. Sentinel: 372 (native) + 8 (F5.1) passed. DAT.AI:
74 passed / 21 skipped (pre-existing) / 3 collection errors
(environment-only, `geoalchemy2`, zero DAT.AI source touched). No
F7-caused regression anywhere.

## No prohibited external action

News Intelligence's real code makes exactly one class of outbound call:
`urllib.request.urlopen()` against the two configured public RSS URLs.
No publish/post/email/messaging function exists anywhere in this
package. No financial execution path is reachable from any F7 code
(confirmed: `create_shadow_entries()` and any order/broker function are
never imported or called anywhere in `tests/f7/` or `news_intelligence/`).
