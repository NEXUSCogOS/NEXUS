# CORPUS_ARCHITECTURE.md

## Overview

The academic corpus is a structurally separate, institutionally-governed research evidence repository. It is implemented as a distinct SQLite database (`academic_corpus.db`) with a different schema from the internal librarian corpus.

## Design Principles

- **Separation of Concerns**: Academic corpus is never mixed with internal documentation; different databases, different table schemas
- **Source Identity First**: All sources identified by stable, verifiable identifiers (DOI > arXiv > URL > content-hash)
- **Provenance Transparency**: Every source carries complete metadata and ingestion lineage
- **Append-Only History**: Retractions and corrections are recorded as events, never silent overwrites
- **Evidence-Gated Relationships**: Citation edges require non-empty evidence strings
- **Domain-Sensitive Weighting**: Source quality ranking varies by question domain (software API, current law, scientific mechanism, market fact)

## Database Schema

### academic_sources (core table)

Columns:
- `source_id` (TEXT PRIMARY KEY): Stable identifier (e.g., "arxiv:2104.08663", "doi:10.1234/x", "content:<sha256>")
- `title`, `authors`, `publication_date`, `journal_or_venue`, `publisher` (TEXT/JSON)
- `doi`, `external_identifiers`, `canonical_url` (identifiers; never all empty)
- `source_type` (TEXT): Closed enum from taxonomy.SourceType (18 categories)
- `peer_review_status`, `verification_status` (ENUM-like TEXT)
- `retrieval_timestamp`, `content_hash`, `license`, `language`, `version` (metadata)
- `retraction_status`, `correction_status` (audit fields, see RETRACTION_AND_CORRECTION_POLICY.md)
- `ingestion_method`, `retrievable_text` (content tracking)
- `created_at` (timestamp)

Indexes:
- `source_type`, `retraction_status`, `doi`

### academic_source_events (append-only audit log)

Columns:
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `source_id`, `event_type` (INGESTED, RETRACTED, CORRECTED, etc.)
- `detail` (event metadata)
- `recorded_at` (timestamp)

Index: `source_id`

**Never UPDATE or DELETE from this table; only INSERT.**

### citation_edges (relationship graph)

Columns:
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `source_from`, `source_to` (references to source_id)
- `edge_type` (CITES, CITED_BY, SUPPORTS, CONTRADICTS, EXTENDS, REPLICATES, CORRECTS, RETRACTS)
- `evidence` (TEXT NOT NULL): Non-empty justification for the edge
- `verified` (INTEGER, boolean flag for human verification)
- `created_at` (timestamp)

Constraint: `UNIQUE(source_from, source_to, edge_type)`

**Edge insertion enforces non-empty evidence via exception (ValueError) — see citation_graph.py:**
```python
if not evidence or not evidence.strip():
    raise ValueError(f"Citation edge requires non-empty evidence")
```

## File Layout

```
systems/librarian/
├── academic/
│   ├── __init__.py
│   ├── taxonomy.py (SourceType enum, domain-sensitive weighting)
│   ├── provenance.py (AcademicProvenance, RetractionStatus, VerificationStatus)
│   ├── identity.py (stable source ID computation)
│   ├── store.py (AcademicStore, SQLite interface)
│   ├── citation_graph.py (CitationEdgeType, edge validation)
│   ├── ingest_real_sources.py (manifest loading, idempotent ingestion)
│   ├── retrieval.py (keyword-based search, lexical only)
│   ├── synthesis.py (claim classification, gap detection, hypotheses)
│   ├── benchmark.py (hand-verified retrieval evaluation)
│   └── real_source_manifest.json (22 real papers from arXiv)
├── runtime/
│   └── academic_research_executor.py (bounded research mission entry point)
├── tests/academic/
│   ├── test_taxonomy_provenance.py
│   ├── test_academic_store_and_ingestion.py
│   ├── test_citation_graph.py
│   ├── test_synthesis.py
│   └── ...
└── [24+ documentation files]
```

## Lifecycle: Source from Ingestion to Retrieval

1. **Manifest Loading** (`ingest_real_sources.py`): 22 real papers fetched from arXiv export API
2. **Provenance Construction** (`provenance.py`): Metadata validated, identity computed
3. **Upsert** (`store.py`): Source inserted/skipped if already exists
4. **Event Recording**: INGESTED event appended to academic_source_events
5. **Retrieval** (`retrieval.py`): Lexical search (case-insensitive substring matching)
6. **Synthesis** (`synthesis.py`): Hits classified by keyword-marker heuristic
7. **Retraction Handling** (`store.py`, RETRACTION_AND_CORRECTION_POLICY.md): Events, never silent updates

## Key Invariants

- **Identity Stability**: A source_id never changes once assigned; if a source is re-ingested, it is skipped (idempotent)
- **No Fabrication**: UNKNOWN remains UNKNOWN; no defaults are invented (see provenance.py)
- **Evidence Gating**: Every citation edge requires a non-empty justification string
- **Audit Trail**: Retraction/correction changes are append-only events, not SQL UPDATEs
- **Corpus Separation**: Academic schema is wholly distinct from internal librarian schema (proven by test_academic_store_and_ingestion.py)
- **Domain Sensitivity**: Evidence weighting is dynamic per question domain, not fixed globally

## Integration Points

- **Federation**: InstitutionalReport returned to NEXUS Federation F2 contract
- **DAT.AI**: Geospatial domain (Q5) benchmark tests DAT.AI corpus policy compatibility
- **Internal Librarian**: Academic executor runs as independent subsystem, never modifies internal corpus
- **Research Loops**: Bounded synthesis (retrieval → classification → gaps → hypotheses) per mission section 20
