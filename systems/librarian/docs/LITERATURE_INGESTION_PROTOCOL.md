# LITERATURE INGESTION PROTOCOL
**NEXUS Federation F3 — 2026-08-27**

Recovered unchanged from the `librarian_rag` donor (commit `d855206`).
Real stages, in order:

1. **Discovery** (`ingestion/discovery.py`): walk configured roots,
   classify every file (`supported|unsupported|unreadable|empty`).
2. **Validation**: only `.md`/`.txt` files with valid UTF-8 and
   non-whitespace content are `supported`.
3. **Provenance capture** (`ingestion/provenance.py`): sha256 of raw
   bytes, mtime, parser/normalizer/chunker version, all at discovery time.
4. **Source-level dedup**: identical file bytes under a different path
   are recorded `skipped_duplicate`, never re-ingested as a second source.
5. **Normalize** (`ingestion/normalize.py`): CRLF→LF, trailing-whitespace
   strip, blank-line collapse — deterministic, idempotent.
6. **Chunk**: paragraph-accumulation up to `CHUNK_TARGET_CHARS` (1200),
   hard-split above `CHUNK_MAX_CHARS` (2000) so no chunk is unbounded.
7. **Chunk-level dedup**: identical chunk text (content_hash) stored once
   in `documents`, referenced by every source's own `chunk_map` row.
8. **Persist**: one transaction spans SQL metadata + `chunk_map` + audit
   log per source — proven transactionally safe
   (`test_transactional_rollback_leaves_no_partial_source`).
9. **Audit**: every action (`created/updated/skipped_unchanged/
   skipped_duplicate/deleted/error`) is logged to `ingestion_log`.

Supports `--dry-run` (census only, zero writes) and is fully idempotent:
re-running over an unchanged corpus creates nothing new (proven:
`test_duplicate_ingestion_is_idempotent`).

## Change since donor recovery

`run_ingest.py`'s `DEFAULT_ROOTS` (two hardcoded, machine-specific paths,
one of which — `~/Librarian` — no longer exists) was removed; roots are
now a required CLI argument. See `LIBRARIAN_DONOR_FORENSIC_REPORT.md`.
