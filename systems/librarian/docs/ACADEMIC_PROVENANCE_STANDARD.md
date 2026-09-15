# ACADEMIC PROVENANCE STANDARD
**NEXUS Federation F3 — 2026-08-27**

## Required fields (per mission section 6) and their real status

| Field | Populated? | Notes |
|---|---|---|
| `document_id` | ✅ always | `sources.source_id` |
| `canonical_path` / `source_uri` | ✅ always | `sources.url` (absolute path at ingestion time) |
| `source_type` | ✅ always | currently always `librarian:librarian` — see `LIBRARIAN_CORPUS_AUDIT.md` |
| `title` | ✅ always | derived from filename |
| `authors` | ❌ never | schema column exists (`sources.author`), never populated by the ingestion pipeline |
| `publication_date` | ❌ never | schema column exists (`sources.published_date`), never populated |
| `doi` | ❌ never | no such column exists at all |
| `retrieval_date` | ✅ always | `sources.created_at` |
| `content_hash` | ✅ per-chunk | `chunk_map.content_hash` (no whole-source hash column) |
| `license/status` | ❌ never | no such column exists |
| `extraction_method` | ✅ always | `parser_version`/`normalizer_version`/`chunker_version` |
| `verification_status` | N/A | Librarian's own ingestion has no independent "verification" step distinct from existence+hash; NEXUS's federation-level evidence resolver (see `evidence/resolver.py`) is what assigns `VERIFIED/PARTIAL/UNVERIFIED/INVALID/MISSING` when a Librarian finding is later ingested |

## Honest gap

Real academic metadata (authors, DOI, journal, license) requires either
(a) a real academic corpus to ingest in the first place (none currently
exists — see `LIBRARIAN_CORPUS_AUDIT.md`), or (b) a metadata-extraction
mechanism this donor never built. Unknown stays `UNKNOWN` — see
`LIBRARIAN_CORPUS_PROVENANCE_REGISTER.json`, where every one of these
fields is the literal string `"UNKNOWN"` for all 93 real rows, never a
fabricated plausible-looking value.

## Compatibility with NEXUS Federation F2's ProvenanceRecord

Librarian's own ingestion-scoped provenance (`parser_version` etc.) is a
DIFFERENT, narrower mechanism than NEXUS's cross-institution
`ProvenanceRecord` graph (F2). The two connect at exactly one point:
`kernel.py`'s evidence-resolution step builds a `source_evidence_file`
`ProvenanceRecord` from whatever a Librarian finding's `evidence_ref`
resolves to on disk — Librarian's own internal chunk/source provenance is
not currently exposed as a separate NEXUS-visible hop (the same disclosed
limitation DAT.AI's own donor pipeline has — see F2's
`PROVENANCE_GRAPH_SPEC.md` LIMITATIONS section).
