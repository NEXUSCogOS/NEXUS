# ACADEMIC_CORPUS_POLICY.md

## Institutional Governance

The academic corpus is subject to explicit, documented policies governing:
- Source acceptance criteria
- Quality assurance mechanisms
- Retraction and correction handling
- Citation relationship verification
- Synthesis integrity standards

## Acceptance Criteria

### Mandatory Fields

Every ingested source must have:
- **Title** (non-empty string)
- **Authors** (list of at least one name)
- **Source Type** (one of 18 closed enum values, see SOURCE_HIERARCHY.md)
- **At least one stable identifier**:
  - DOI (preferred), OR
  - arXiv ID, OR
  - ISBN/standards ID, OR
  - Canonical URL, OR
  - Content hash (last resort fallback)
  - Never a filename alone

### Metadata Completeness

- Unknown fields: Must be set to literal string "UNKNOWN", never fabricated with defaults
- Retrieval timestamp: When the source was fetched/added
- Content hash: SHA256 of extractable text (enables deduplication)
- Ingestion method: How the source entered the corpus (e.g., "arxiv_export_api", "manual_doi_lookup")

### Verification Status

Sources are classified by confidence level:
- `VERIFIED`: Human confirmation of peer-review status and metadata accuracy
- `PARTIAL`: Some metadata confirmed, peer-review status inferred
- `UNVERIFIED`: Metadata extracted automatically, human verification pending
- `INVALID`: Source failed validation checks
- `MISSING`: Metadata unavailable despite retrieval attempts

Current ingestion (22 papers from arXiv): classified as ACADEMIC_PREPRINT with PARTIAL verification (metadata verified verbatim against arXiv feed, peer-review status not independently confirmed).

## Quality Assurance

### Deduplication

Sources are deduplicated by content-hash and cross-identifier matching:
1. If a new source has DOI matching an existing source, skip (idempotent ingestion)
2. If content-hash matches, flag as potential duplicate for manual review
3. External identifier conflicts (e.g., same arXiv ID) trigger skip

See DEDUPLICATION_PROTOCOL.md for detailed mechanism.

### Retraction Handling

- Retractions are **recorded as events**, not silent database updates
- Each retraction event includes:
  - Source ID
  - Event type: RETRACTED
  - Detail: Reason for retraction (e.g., "published erratum", "author request", "publisher notice")
  - Timestamp
- Original INGESTED event remains in audit log (never deleted)
- Retracted sources excluded from retrieval by default (see RETRIEVAL_ARCHITECTURE.md)

### Correction Tracking

- Corrections to metadata are append-only events
- Example: "author list corrected per published errata" → CORRECTED event
- Synthesis runs should note when evidence comes from retracted or heavily-corrected sources

## Domain-Sensitive Weighting

Source quality ranking varies by question type:

| Domain | Preferred | Secondary | Avoided |
|--------|-----------|-----------|---------|
| SOFTWARE_API_BEHAVIOR | Official Technical Documentation | Technical Report | News |
| CURRENT_LAW_OR_REGULATION | Primary Source (statute, regulation, court record) | Government/Intergovernmental | News |
| SCIENTIFIC_MECHANISM | Meta-Analysis | Systematic Review | News |
| MARKET_FACT | Primary Source (earnings report, market data) | Industry Research | Commentary |
| GENERAL | Meta-Analysis, Systematic Review | Peer-Reviewed Journal | News, Secondary Web |

See TAXONOMY.md and academic/taxonomy.py for full rank table.

## Citation Policy

- Citation edges (structural and semantic) require explicit, non-empty evidence
- Structural edges (CITES, CITED_BY): Evidence is the location in reference list
- Semantic edges (SUPPORTS, CONTRADICTS, EXTENDS, etc.): Evidence is the textual basis for the claim
- Unverified edges are stored (verified=0) but flagged in synthesis reports
- No edges are inferred from co-occurrence alone

See CITATION_GRAPH_SPEC.md.

## Synthesis Integrity

When evidence is presented in synthesis reports:
1. Claim support is classified using keyword-marker heuristic (disclosed in basis_for_status)
2. Confidence is noted as heuristic classification, not semantic entailment
3. If support markers are absent, status is INSUFFICIENT_EVIDENCE, not fabricated CONSENSUS
4. Research gaps are strictly typed (CORPUS_GAP / RETRIEVAL_FAILURE / EVIDENCE_GAP / LITERATURE_GAP / OPEN_SCIENTIFIC_QUESTION)
5. Contradictory evidence is never hidden; MIXED status is explicitly reported

See EVIDENCE_SYNTHESIS_METHOD.md and CONTRADICTORY_EVIDENCE_PROTOCOL.md.

## Ingestion Governance

Sources are ingested via:
- **Real Source Manifest** (JSON file): 22 arXiv papers, verbatim metadata from export API
- **Idempotent Ingestion**: Running ingest_all() twice yields created=22 on first run, created=0 on second (no duplicates)
- **Manual Entry**: Future ad-hoc sources via API will require provenance object validation
- **Embargo**: No News sources are automatically ingested; NEWS type is available but not populated

## Audit & Compliance

- Every change to academic_corpus.db is logged in academic_source_events (append-only)
- academic_sources table has created_at timestamp; no sources lack ingestion record
- Test suite (test_academic_store_and_ingestion.py) verifies:
  - Manifest loads ≥20 real papers
  - Ingestion is idempotent
  - Every ingested source has stable identifier (arxiv: or doi:)
  - No empty retrievable_text
  - Retraction status changes recorded as events (not silent UPDATE)
