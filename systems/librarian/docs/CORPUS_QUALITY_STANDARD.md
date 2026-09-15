# CORPUS QUALITY STANDARD
**NEXUS Federation F3 — 2026-08-27**

See `LIBRARIAN_CORPUS_AUDIT.md` for the full, real audit this standard is
derived from. Summary of the standard itself:

## Structural quality gates already enforced (real, mechanized)

1. **No corrupt content ingested.** `ingestion/discovery.py` classifies
   every file as `supported|unsupported|unreadable|empty` BEFORE
   ingestion; unreadable/empty files are recorded and excluded, never
   silently ingested as blank/garbage content.
2. **No duplicate files re-ingested as distinct sources.**
   Source-level dedup (exact byte match) is enforced at discovery time.
3. **No duplicate content stored twice.** Chunk-level content-hash dedup
   ensures identical text is stored once regardless of how many sources
   contain it.
4. **Every source/chunk carries reproducibility metadata**
   (`parser_version`/`chunker_version`) — a future processing change is
   detectable as version drift, not silently inconsistent.
5. **Orphan detection is provably zero** — re-verified this mission via
   direct `LEFT JOIN` query (`LIBRARIAN_CORPUS_AUDIT.md` section 4).

## What this standard does NOT (yet) enforce, honestly

- **No source-quality/peer-review classification exists.** Every real
  source in the current corpus is classified `TECHNICAL DOCUMENTATION`
  (see `SOURCE_HIERARCHY.md`) — there is no mechanism to distinguish a
  peer-reviewed paper from a blog post if one were ingested, because none
  ever has been.
- **No completeness/coverage scoring exists.** "Topic coverage" in
  `LIBRARIAN_CORPUS_AUDIT.md` is reported qualitatively (self-referential
  vs. domain-relevant), not as a fabricated percentage.
- **No staleness policy exists beyond the single ingestion timestamp**
  already recorded — there is no automatic re-verification schedule.

No arbitrary quality score (e.g. "87% corpus health") is ever computed
anywhere in this codebase.
