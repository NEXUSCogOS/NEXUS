# ACADEMIC_PROVENANCE_STANDARD.md

## Provenance Definition

Provenance is the complete metadata lineage of an academic source. It captures:
- **Descriptive metadata**: title, authors, publication details
- **Identifiers**: stable references to the source (DOI, arXiv, URL, hash)
- **Ingestion lineage**: when, how, and by whom the source was added
- **Verification status**: confidence in metadata accuracy
- **Retraction/correction history**: append-only audit trail

## Required Fields

Every source in the academic corpus must have a complete AcademicProvenance object with these fields:

### Identity (at least one required)

| Field | Type | Requirement | Example |
|-------|------|-------------|---------|
| doi | STRING | ≥1 identifier required | "10.1038/nature12373" |
| external_identifiers | JSON dict | {arxiv, pmid, pmcid, isbn, ...} | {"arxiv": "2104.08663"} |
| canonical_url | URL | Full URL or "UNKNOWN" | "https://arxiv.org/abs/2104.08663" |
| source_id | STRING (computed) | Stable ID from identity.py | "arxiv:2104.08663" |

**Validation**: AcademicProvenance requires ≥1 of (doi != "UNKNOWN", external_identifiers non-empty, canonical_url != "UNKNOWN"). Sources lacking all three are rejected (see test_provenance_requires_at_least_one_identifier).

### Descriptive Metadata

| Field | Type | Requirement | Example |
|-------|------|-------------|---------|
| title | STRING | Non-empty | "BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models" |
| authors | LIST[STRING] | ≥1 author | ["Thakur, Nandan", "Reimers, Nils", ...] |
| publication_date | STRING (ISO 8601) | Date or "UNKNOWN" | "2021-04-08" |
| journal_or_venue | STRING | Journal/conference name or "UNKNOWN" | "arXiv" |
| publisher | STRING | Publisher or "UNKNOWN" | "arXiv" |

### Source Classification

| Field | Type | Requirement | Example |
|-------|------|-------------|---------|
| source_type | ENUM | One of 18 SourceType values | "ACADEMIC_PREPRINT" |
| peer_review_status | STRING | "PEER_REVIEWED", "UNREVIEWED", "PREPRINT", "UNKNOWN" | "UNREVIEWED" |
| verification_status | ENUM | VERIFIED, PARTIAL, UNVERIFIED, INVALID, MISSING | "PARTIAL" |

### Content & Access

| Field | Type | Requirement | Example |
|-------|------|-------------|---------|
| retrievable_text | STRING | First 500+ chars of abstract/full text | "Abstract text..." |
| content_hash | STRING (SHA256) | Computed hash of retrievable_text | "abc123def456..." |
| license | STRING | License or "UNKNOWN" | "CC-BY-4.0", "PUBLIC_DOMAIN" |
| language | STRING (ISO 639-1) | Language code or "UNKNOWN" | "en" |
| version | STRING | Version identifier or "UNKNOWN" | "1", "v2", "UNKNOWN" |

### Ingestion & Audit

| Field | Type | Requirement | Example |
|-------|------|-------------|---------|
| ingestion_method | STRING | How source was acquired | "arxiv_export_api", "doi_lookup", "manual_entry" |
| retrieval_timestamp | ISO 8601 | When metadata was fetched | "2026-08-27T14:30:00Z" |
| created_at | ISO 8601 (auto) | Timestamp of first insert | "2026-08-27T14:30:00Z" |

### Retraction & Correction (Audit Trail)

| Field | Type | Requirement | Example |
|-------|------|-------------|---------|
| retraction_status | ENUM | ACTIVE, CORRECTED, RETRACTED, SUPERSEDED, UNKNOWN | "ACTIVE" |
| correction_status | STRING | Append-only audit note or "NONE" | "NONE" or "RETRACTION_NOTED_NO_FURTHER_CORRECTION_DETAIL" |

**Policy**: When retraction_status is RETRACTED, correction_status is automatically set to a marker (never NONE). The original source record is never deleted; retraction is recorded in academic_source_events table as an append-only event.

## Data Type Specifications

### AcademicProvenance (Pydantic Model)

```python
class AcademicProvenance(BaseModel):
    source_id: str                      # stable computed ID
    title: str                          # non-empty
    authors: list[str]                  # non-empty
    publication_date: str = "UNKNOWN"   # ISO 8601 or literal "UNKNOWN"
    journal_or_venue: str = "UNKNOWN"
    publisher: str = "UNKNOWN"
    doi: str = "UNKNOWN"
    external_identifiers: dict = {}     # may be empty but not None
    canonical_url: Optional[str] = "UNKNOWN"
    source_type: SourceType             # required, from closed enum
    peer_review_status: str = "UNKNOWN"
    retrieval_timestamp: str            # ISO 8601
    content_hash: str                   # SHA256 hex
    license: str = "UNKNOWN"
    language: str = "UNKNOWN"
    version: str = "UNKNOWN"
    retraction_status: RetractionStatus = RetractionStatus.ACTIVE
    correction_status: str = "NONE"
    ingestion_method: str               # required, describes acquisition
    verification_status: VerificationStatus  # required

    # Validators:
    # 1. @field_validator: requires ≥1 of (doi, external_identifiers, canonical_url)
    # 2. @model_validator: auto-sets correction_status if retracted
```

### Enum: RetractionStatus

```python
class RetractionStatus(str, Enum):
    ACTIVE = "ACTIVE"           # source is valid, not retracted
    CORRECTED = "CORRECTED"     # source has published correction/erratum
    RETRACTED = "RETRACTED"     # source is formally retracted
    SUPERSEDED = "SUPERSEDED"   # source is superseded by newer version
    UNKNOWN = "UNKNOWN"         # retraction status not known
```

### Enum: VerificationStatus

```python
class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"       # human-confirmed accurate
    PARTIAL = "PARTIAL"         # some metadata confirmed, some inferred
    UNVERIFIED = "UNVERIFIED"   # metadata extracted automatically, unreviewed
    INVALID = "INVALID"         # metadata failed validation
    MISSING = "MISSING"         # metadata unavailable despite attempts
```

## UNKNOWN Policy

**Critical Rule**: Fields with unknown or missing values are set to the literal string "UNKNOWN", never:
- Omitted (None)
- Set to empty string ""
- Set to default placeholder like "N/A" or "TBD"
- Inferred with AI/LLM

Example:
```python
prov = AcademicProvenance(
    source_id="arxiv:2104.08663",
    title="BEIR: A Heterogeneous Benchmark...",
    authors=["Thakur, Nandan", ...],
    external_identifiers={"arxiv": "2104.08663"},
    # All unknown fields explicitly set to "UNKNOWN":
    doi="UNKNOWN",
    publication_date="UNKNOWN",
    journal_or_venue="UNKNOWN",
    publisher="UNKNOWN",
    license="UNKNOWN",
    version="UNKNOWN",
    # ...
)
```

This ensures:
1. No silent data loss (queries can find "UNKNOWN" fields)
2. No AI hallucination (UNKNOWN is not a real value)
3. Audit clarity (operator sees exactly what was and wasn't extracted)

Tested in test_provenance_unknown_fields_stay_unknown_not_fabricated.

## Ingestion Process

1. **Manifest Load** (ingest_real_sources.py): JSON file with 22 papers from arXiv
2. **Provenance Build**: For each paper, create AcademicProvenance object:
   - Extract: title, authors, abstract (summary), arxiv_id, publication_date
   - Map to standard fields: arxiv_id → external_identifiers.arxiv, source_type → ACADEMIC_PREPRINT
   - Set unknowns: doi="UNKNOWN", journal_or_venue="UNKNOWN", etc.
3. **Identity Computation** (identity.py): compute_source_id() returns "arxiv:XXXX" (arxiv preferred)
4. **Validation** (provenance.py): Pydantic validator checks ≥1 identifier present
5. **Upsert** (store.py): Insert or skip if source_id already exists
6. **Event Recording**: INGESTED event appended to academic_source_events

## Retraction/Correction Workflow

When a retraction is discovered:

1. **Identify Source**: source_id (e.g., "arxiv:2104.08663")
2. **Record Event**: Call store.set_retraction_status(source_id, "RETRACTED", detail="published erratum")
3. **Append Event**: New row in academic_source_events with:
   - event_type="RETRACTED"
   - detail="published erratum"
   - recorded_at=NOW
4. **Update Status**: academic_sources.retraction_status ← "RETRACTED"
5. **Auto-Note**: correction_status ← "RETRACTION_NOTED_NO_FURTHER_CORRECTION_DETAIL" (Pydantic auto-validator)
6. **Preserve History**: Original INGESTED event remains in audit log (never deleted)

Test: test_retraction_status_change_is_recorded_as_event_not_silent_overwrite confirms events accumulate.

## Quality Assurance

- **Spot Checks**: Sample 10% of ingested sources, verify title/authors/abstract verbatim against original
- **Deduplication**: Before insertion, check DOI and arXiv ID against existing sources
- **Metadata Validation**: All required fields present before upsert
- **Content Hash**: SHA256 of retrievable_text enables duplicate detection
- **Timestamping**: All ingestion events timestamped in UTC

Current corpus (22 papers) has:
- 100% identity completeness (all arxiv:XXXX)
- 100% spot-check accuracy (manually verified against arXiv feed)
- 100% metadata coverage (title, authors, publication_date, abstract all present)
