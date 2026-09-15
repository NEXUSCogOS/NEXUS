# CORPUS ARCHITECTURE
**NEXUS Federation F3 — 2026-08-27**

## Schema (recovered from donor `librarian_rag`, unchanged)

- `sources`: one row per ingested file — title, source_type, url, author
  (unpopulated), published_date (unpopulated), tags, metadata (JSON:
  provenance — root/rel_path/source_hash/parser_version/etc).
- `documents`: canonical, deduplicated chunk content, keyed by
  `content_hash` (UNIQUE) — owned by the synthetic `_canonical` bucket,
  decoupled from any one source (see `ingestion/pipeline.py` docstring
  for why: a real bug this exact design fixed, per the donor's own commit
  message).
- `chunk_map`: per-source ordered chunk index → content_hash — lets each
  source reconstruct its full text independently even when chunks are
  shared with other sources.
- `ingestion_log`: append-only audit trail of every ingest action
  (created/updated/skipped_unchanged/skipped_duplicate/deleted/error).
- `query_history`: schema exists, currently unpopulated (no query
  capability existed in the donor to write to it — see
  `LIBRARIAN_LIMITATIONS.md`; `retrieval/lexical_search.py`, built this
  mission, does not yet log to it either — a stated gap, not silently
  ignored).

## Real current corpus (as of 2026-08-09 ingestion, preserved byte-identical)

93 sources, 297 canonical documents, 371 chunk_map entries, 0 orphans, 0
corrupt files. See `LIBRARIAN_CORPUS_AUDIT.md` for the full audit and
`LIBRARIAN_CORPUS_PROVENANCE_REGISTER.json` for the per-source register.

## Content addressing

Every chunk is keyed by `sha256(normalized_text.strip())`. Identical
content appearing in multiple sources is stored once — proven by the real
corpus's 74 duplicate-content chunks correctly collapsing to shared
`documents` rows while each source's own `chunk_map` still reconstructs
independently (tested: `test_reconstruction_survives_shared_chunks`).
