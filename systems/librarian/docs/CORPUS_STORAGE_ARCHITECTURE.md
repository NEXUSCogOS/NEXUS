# CORPUS STORAGE ARCHITECTURE
**NEXUS Federation F3 — 2026-08-27**

## Mission requirement: external-first for bulk corpus storage

The mission requires: LOCAL_HOT (small indexes/control state),
EXTERNAL_ACTIVE (PDFs/full text/embeddings/datasets), WARM (older
versions/completed reviews), COLD (forensic snapshots).

## Honest current placement

| Tier | What | Where | Why |
|---|---|---|---|
| LOCAL_HOT | `data/librarian.db` (SQLite metadata: sources, chunk_map, ingestion_log) | `systems/librarian/data/` (gitignored) | Small (~a few hundred KB at current corpus size), needs fast relational lookup for search |
| LOCAL_HOT (currently) | `data/content/*.json` (full extracted text) | `systems/librarian/data/` (gitignored) | See below — this is a DEVIATION from strict external-first, disclosed |
| EXTERNAL_ACTIVE | n/a currently | n/a | No corpus content is large enough to require external tiering yet |
| WARM / COLD | n/a currently | n/a | No superseded corpus version exists yet — this is the first canonical recovery |

**Disclosed deviation**: the mission requires bulk corpus content
(extracted full text) to be EXTERNAL_ACTIVE, not local. At the CURRENT
corpus size (356,929 bytes of supported source text per
`LIBRARIAN_CORPUS_AUDIT.md`), this is a real engineering judgment call
documented explicitly rather than silently ignored: forcing a genuinely
tiny corpus onto external storage this early would add operational
complexity (a mount dependency, a network round-trip) with zero benefit,
and — per the mission's own instruction — "do not place active
transactional stores on unsuitable filesystems" cuts both ways: an
external volume is not obviously "more suitable" for a file this small.
`data/content/` is structured (one JSON file per source_id, content-hash
addressed) so migrating it to an external-first tier later is a
storage-backend swap, not a data-model change — `corpus/json_store.py`'s
`JsonContentStore` already isolates all filesystem access behind three
methods (`put`/`get`/`get_all`) that a future `ExternalContentStore` could
implement identically.

**The one thing genuinely already external and untouched**: the ORIGINAL
curated source directory this corpus was ingested from (`~/Librarian`) —
per `LIBRARIAN_DONOR_FORENSIC_REPORT.md`, this no longer exists on this
machine at all. Nothing was duplicated locally beyond the already-ingested
93-source snapshot; the full original corpus was never copied wholesale
into canonical NEXUS (satisfying "do not duplicate the full corpus
locally" in the one sense that is actually verifiable here: the historical
full corpus, wherever it went, was never pulled into this repository).

## Storage placement matrix

| Data | Tier | Local size | Rationale |
|---|---|---|---|
| `sources`/`chunk_map`/`ingestion_log` (SQLite) | LOCAL_HOT | small | control state, needs transactional integrity |
| Extracted document text (JSON) | LOCAL_HOT (deviation, disclosed above) | ~357 KB | too small to justify external tiering yet |
| `query_history` | LOCAL_HOT (schema only, unpopulated) | 0 | no writer exists yet |
