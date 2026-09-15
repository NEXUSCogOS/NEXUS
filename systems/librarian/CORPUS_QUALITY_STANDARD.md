# CORPUS_QUALITY_STANDARD.md

## Quality Metrics

The academic corpus is measured against five key quality dimensions:

### 1. Completeness (Provenance Coverage)

**Metric**: % of sources with ≥4 of these 5 fields non-UNKNOWN:
- publication_date
- journal_or_venue
- authors (non-empty list)
- publisher or peer_review_status confirmed
- doi or official identifier

**Current Baseline** (22 papers): 100% have at least arxiv ID and authors; 95% have publication date and venue; 20% have DOI.

**Target**: ≥90% for production corpus

### 2. Identity Stability

**Metric**: % of sources with stable, verifiable identifiers (not filename-based)

**Standard**: Every source_id must be one of:
- doi:XXXX
- arxiv:XXXX
- isbn:XXXX
- standards_id:XXXX
- url:<canonical_url>
- content:<sha256_hash>

Never: filename-based, temporary URLs, or unversioned paths.

**Current Baseline**: 100% (22/22 are arxiv:XXXX)

### 3. Deduplication Accuracy

**Metric**: False positive rate (same paper ingested twice) and false negative rate (distinct papers marked duplicate)

**Standard**:
- False positive rate: <0.1% (ingestion must be idempotent)
- False negative rate: <5% (deduplication must be sensitive enough to catch true duplicates)
- Mechanism: content-hash + DOI/arxiv cross-check

**Current Baseline**: 0% false positives (test_real_ingestion_is_idempotent confirms idempotency)

### 4. Retraction Coverage

**Metric**: % of known-retracted papers in corpus that are flagged retraction_status=RETRACTED

**Standard**: ≥95% (within 30 days of public retraction notice)

**Current Baseline**: 0 retracted papers in corpus (no retractions in 22-paper sample)

**Mechanism**: Manual monitoring of arXiv retraction feed; event-based updates (never silent overwrites)

### 5. Metadata Accuracy (Spot-Check Audits)

**Metric**: % of spot-checked sources whose title, authors, and venue match original publication

**Standard**: ≥98%

**Current Baseline** (22 papers): 100% (verified manually against arXiv export API verbatim)

## Verification Protocol

### Automated Checks (at ingestion time)

1. **Identity Check**: Source must have ≥1 stable identifier
2. **Completeness Check**: ≥3 of {title, authors, publication_date, journal_or_venue, publisher}
3. **Retrieval Check**: retrievable_text must be non-empty
4. **Deduplication Check**: DOI and arxiv cross-index for duplicates
5. **Retraction Check**: Query arXiv/PubMed retraction feeds (if available)

### Manual Verification (sampling)

- Every 100 sources ingested: audit 10 random samples
- Verification includes:
  - Title and abstract match original source
  - Author list is complete (not truncated)
  - Publication date is accurate
  - Journal/venue is correctly identified
- Mark verified sources as verification_status=VERIFIED

### Continuous Monitoring

- Monthly audit: 5% random sample re-verified
- Retraction feed monitoring: real-time PubMed/arXiv feed for retraction notices
- Event log review: check for anomalies in ingestion_method or verification_status changes

## Benchmark Standards

Retrieval quality is measured against hand-verified benchmark questions (see RETRIEVAL_BENCHMARK_PROTOCOL.md):

| Metric | Target | Current |
|--------|--------|---------|
| Recall@5 | ≥0.8 | 1.0 (5/5 questions) |
| Precision@5 | ≥0.6 | 0.4-0.8 (varies by question) |
| MRR (Mean Reciprocal Rank) | ≥0.8 | 1.0 |
| Distractors (false positives) | ≤0.2 per query | 0-1 per query |

## Citation Quality

When citation edges are populated (future missions):

| Metric | Target |
|--------|--------|
| % edges with evidence strings | 100% |
| % verified edges (human-checked) | ≥30% (sampling) |
| False positive rate (wrong relationship type) | <5% |
| Cross-validation with reference managers | ≥95% match |

Current state: 0 edges populated (reference extraction not performed this mission).

## Synthesis Quality

When synthetic results are generated (every research mission):

| Metric | Standard |
|--------|----------|
| Every claim has basis_for_status disclosed | 100% |
| Keyword-marker heuristic noted (not semantic entailment) | 100% |
| INSUFFICIENT_EVIDENCE used when markers absent | 100% (tested) |
| Contradictory evidence never hidden | 100% (tested) |
| Research gap types correctly distinguished | 100% (tested) |

## Escalation Criteria

Quality issues requiring escalation to Librarian operator:

1. **Ingestion Failure**: ≥10% of manifest sources fail identity validation
2. **Deduplication Anomaly**: >5% false negative rate detected in spot checks
3. **Metadata Corruption**: Verification sampling shows <95% accuracy
4. **Retraction Lag**: Retracted paper remains retrievable >30 days after public notice
5. **Synthesis Degradation**: Benchmark recall or precision drops >10% from baseline

## Documentation References

- DEDUPLICATION_PROTOCOL.md: Duplicate detection mechanism
- RETRIEVAL_BENCHMARK_PROTOCOL.md: Hand-verified benchmark questions
- EVIDENCE_SYNTHESIS_METHOD.md: Claim classification standards
- ACADEMIC_PROVENANCE_STANDARD.md: Metadata field requirements
