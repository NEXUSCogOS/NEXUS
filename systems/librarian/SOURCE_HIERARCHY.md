# SOURCE_HIERARCHY.md

## Closed Taxonomy of Source Types

The academic corpus uses a closed, non-extensible set of 18 source categories. This prevents ambiguity and ensures domain-sensitive weighting is predictable.

### Source Type Enum (academic/taxonomy.py)

```python
class SourceType(str, Enum):
    PRIMARY_SOURCE = "PRIMARY_SOURCE"
    PEER_REVIEWED_JOURNAL = "PEER_REVIEWED_JOURNAL"
    PEER_REVIEWED_CONFERENCE = "PEER_REVIEWED_CONFERENCE"
    SYSTEMATIC_REVIEW = "SYSTEMATIC_REVIEW"
    META_ANALYSIS = "META_ANALYSIS"
    ACADEMIC_BOOK = "ACADEMIC_BOOK"
    ACADEMIC_PREPRINT = "ACADEMIC_PREPRINT"
    GOVERNMENT_REPORT = "GOVERNMENT_REPORT"
    INTERGOVERNMENTAL_REPORT = "INTERGOVERNMENTAL_REPORT"
    STANDARDS_BODY = "STANDARDS_BODY"
    UNIVERSITY_TECHNICAL_REPORT = "UNIVERSITY_TECHNICAL_REPORT"
    OFFICIAL_TECHNICAL_DOCUMENTATION = "OFFICIAL_TECHNICAL_DOCUMENTATION"
    INDUSTRY_RESEARCH = "INDUSTRY_RESEARCH"
    TECHNICAL_REPORT = "TECHNICAL_REPORT"
    NEWS = "NEWS"
    SECONDARY_WEB = "SECONDARY_WEB"
    INTERNAL_NEXUS_DOCUMENT = "INTERNAL_NEXUS_DOCUMENT"
    UNKNOWN = "UNKNOWN"
```

### Definitions

**PRIMARY_SOURCE**
- Direct evidence: statute, regulation, court record, earnings report, lab data, survey result
- Example: "2009 Federal Reserve Interest Rate Decision"
- Authority: High (direct authority), Context-dependent quality

**PEER_REVIEWED_JOURNAL**
- Peer-reviewed journal article (impact factor or recognized venue)
- Example: Nature, Science, JAMA, ACL
- Authority: Very High, Subject to field norms

**PEER_REVIEWED_CONFERENCE**
- Peer-reviewed conference paper (top-tier: NeurIPS, ICML, SIGMOD; or peer-reviewed regional)
- Example: "Attention Is All You Need" (NIPS 2017)
- Authority: Very High, Field-specific

**SYSTEMATIC_REVIEW**
- Systematic review of literature following pre-registered protocol
- Example: Cochrane reviews
- Authority: Very High (meta-methodology), Often specific to health/social sciences

**META_ANALYSIS**
- Statistical meta-analysis combining results from multiple studies
- Example: "Meta-analysis of 47 RCTs on X treatment"
- Authority: Very High (statistical synthesis), Assumes quality of component studies

**ACADEMIC_BOOK**
- Scholarly book from academic press (not trade press)
- Example: "Deep Learning" by Goodfellow, Bengio, Courville
- Authority: High, Vetted by publisher

**ACADEMIC_PREPRINT**
- Pre-publication manuscript on arXiv, bioRxiv, medRxiv, etc.
- Example: arXiv papers
- Authority: Medium (not peer-reviewed yet), Under review or rejected elsewhere
- Note: Current corpus (22 papers) all classified as ACADEMIC_PREPRINT, verification_status=PARTIAL

**GOVERNMENT_REPORT**
- Report from national government agency (e.g., NIH, NSF, EPA, DOJ)
- Example: "FBI Intelligence Report on Cybersecurity Trends"
- Authority: High (official source), Domain-specific credibility

**INTERGOVERNMENTAL_REPORT**
- Report from international organization (UN, OECD, World Bank, WHO)
- Example: IPCC Climate Report
- Authority: Very High (consensus body), Often synthesizes primary + peer-reviewed

**STANDARDS_BODY**
- Published standard from ISO, IEEE, NIST, IETF, W3C, etc.
- Example: ISO 27001 (Information Security Management)
- Authority: Very High (industry/engineering consensus), Mandatory in some domains

**UNIVERSITY_TECHNICAL_REPORT**
- Technical report from university (not peer-reviewed journal/conference)
- Example: MIT TR-123, Stanford Computer Systems Lab report
- Authority: Medium-High (institution credibility), Often pre-publication

**OFFICIAL_TECHNICAL_DOCUMENTATION**
- Official documentation from software/hardware vendor (e.g., Python docs, React docs, AWS docs)
- Example: "Python Official Documentation for asyncio"
- Authority: Very High for questions about software behavior, Can be out-of-date for legacy systems
- Note: Preferred over PEER_REVIEWED_JOURNAL for SOFTWARE_API_BEHAVIOR domain

**INDUSTRY_RESEARCH**
- Research report from private company/analyst firm (e.g., McKinsey, Gartner, company research labs)
- Example: "Gartner Magic Quadrant for Data Analytics Platforms"
- Authority: Medium (commercial incentive), Domain-specific for market trends

**TECHNICAL_REPORT**
- General technical report (can be from any organization)
- Example: RAND Corporation report, think tank white paper
- Authority: Medium (depends on source credibility), Catch-all category

**NEWS**
- News article, blog post, commentary from non-academic journalism
- Example: Wall Street Journal article, Technology review blog
- Authority: Low-Medium (timely but biased), Not fact-checked systematically
- Policy: NEWS sources are NOT automatically ingested; corpus is currently NEWS-free

**SECONDARY_WEB**
- Blog, wiki, forum, unvetted web content
- Example: Wikipedia article, Reddit discussion, Medium post
- Authority: Low (no systematic review), Useful for discovery only
- Policy: SECONDARY_WEB sources are NOT ingested into academic corpus

**INTERNAL_NEXUS_DOCUMENT**
- Documentation from NEXUS internal knowledge base (federated reports, prior research)
- Example: "NEXUS Librarian F2 findings on distributed systems resilience"
- Authority: Medium (institutional knowledge), Subject to NEXUS review cycle

**UNKNOWN**
- Source type could not be determined
- Authority: Lowest, marks incomplete ingestion
- Policy: Sources with UNKNOWN source_type are flagged for manual verification

## Hierarchy (Authority Ordering)

From highest to lowest default authority:

1. **Consensus/Synthesis**: META_ANALYSIS, SYSTEMATIC_REVIEW, INTERGOVERNMENTAL_REPORT
2. **Rigorous Peer Review**: PEER_REVIEWED_JOURNAL, PEER_REVIEWED_CONFERENCE, ACADEMIC_BOOK
3. **Government/Standards**: GOVERNMENT_REPORT, STANDARDS_BODY
4. **Primary/Official**: PRIMARY_SOURCE, OFFICIAL_TECHNICAL_DOCUMENTATION
5. **Institutional/Technical**: UNIVERSITY_TECHNICAL_REPORT, TECHNICAL_REPORT, INDUSTRY_RESEARCH
6. **Pre-review**: ACADEMIC_PREPRINT, INTERNAL_NEXUS_DOCUMENT
7. **Web/News**: NEWS, SECONDARY_WEB
8. **Unknown**: UNKNOWN

## Domain-Sensitive Overrides

This ordering is *not* universal. Different question domains rerank sources:

**SOFTWARE_API_BEHAVIOR**
- Preferred: OFFICIAL_TECHNICAL_DOCUMENTATION, UNIVERSITY_TECHNICAL_REPORT
- Secondary: PEER_REVIEWED_JOURNAL
- Rationale: APIs are defined by their official specification; old journal articles may not match current behavior

**CURRENT_LAW_OR_REGULATION**
- Preferred: PRIMARY_SOURCE (statute, regulation, court record)
- Secondary: GOVERNMENT_REPORT, INTERGOVERNMENTAL_REPORT
- Avoided: SECONDARY_WEB, NEWS
- Rationale: Law is what the statute says, not commentary about it

**SCIENTIFIC_MECHANISM**
- Preferred: META_ANALYSIS, SYSTEMATIC_REVIEW
- Secondary: PEER_REVIEWED_JOURNAL, PEER_REVIEWED_CONFERENCE
- Rationale: Mechanism questions benefit from synthesis of multiple studies; single studies have high variance

**MARKET_FACT**
- Preferred: PRIMARY_SOURCE (earnings, filings, price data)
- Secondary: INDUSTRY_RESEARCH, GOVERNMENT_REPORT
- Avoided: ACADEMIC_PREPRINT, SECONDARY_WEB
- Rationale: Market facts are data-driven; pre-review papers are too slow for market data

**GENERAL** (default)
- Order: META_ANALYSIS > SYSTEMATIC_REVIEW > PEER_REVIEWED_JOURNAL > ACADEMIC_BOOK > GOVERNMENT_REPORT > others

See academic/taxonomy.py `_DEFAULT_RANK` and `_DOMAIN_OVERRIDES` for exact weights.

## Implementation

Source type is stored as immutable TEXT enum in academic_sources.source_type. Ingestion validates against SourceType enum:

```python
if source_type not in [st.value for st in SourceType]:
    raise ValueError(f"Unknown source_type: {source_type}")
```

Query weighting uses `evidence_weight(source_type, domain)` to rank sources dynamically:

```python
def evidence_weight(source_type: SourceType, domain: QuestionDomain = QuestionDomain.GENERAL) -> int:
    # Lower number = higher weight (preferred)
    # Uses domain overrides if available, falls back to default rank
    rank = _DOMAIN_OVERRIDES.get(domain, {}).get(source_type) or _DEFAULT_RANK.get(source_type, 999)
    return rank
```

Lower rank value = higher confidence = appears earlier in search results when weighted by source quality.
