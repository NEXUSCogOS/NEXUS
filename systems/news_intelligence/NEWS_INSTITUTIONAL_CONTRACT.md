# NEWS INTELLIGENCE INSTITUTIONAL CONTRACT
**NEXUS Federation F7 — 2026-08-28**

## Registration

```python
# ingress/contract_registry.py
"news_intelligence": ContractRegistration(
    validate_fn=validate_generic_report,
    known_schema_versions=frozenset({"1.0.0"}),
)
```

Same generic contract Librarian/Sentinel already use — no News-specific
NEXUS parser (mission section 22's explicit instruction). `institution_type
= "external_world_intelligence"` registered in `kernel.py::
INSTITUTION_TYPES`.

## Institutional boundary (mission section 3)

**News Intelligence owns:** external-source acquisition, article/document
normalization, source metadata, entity extraction, entity resolution,
event extraction, event clustering, duplicate detection, novelty
detection, trend/emergence detection, source diversity assessment,
source reliability metadata, event confidence, event provenance, event
freshness.

**News Intelligence does NOT own** (and this implementation does not
touch): financial valuation (Sentinel), academic/policy research
(Librarian), geospatial analysis (DAT.AI), global prioritization
(NEXUS), video production (YouTube — confirmed via forensic search to be
a wholly separate, downstream system, see NEWS_F7_FORENSIC_REPORT.md).

## Authority ceiling

`OBSERVE` / `ANALYSE` only. News Intelligence never requests or holds
authority to publish externally, execute a financial transaction, or
modify another institution — enforced structurally by the same
`AuthorityLevel` ladder proven in F5/F6 (`authority/model.py`).

## Real capability statuses (see `institutional_report.py::build_news_report`)

| Capability | Lifecycle | Basis |
|---|---|---|
| `event_acquisition` | TESTED | Real RSS acquisition against 2 configured, live, public sources |
| `entity_resolution` | TESTED | Deterministic dictionary match against Sentinel's real companies table + fixed VN province list, word-boundary matched |
| `event_construction` | TESTED | Deterministic keyword-based type classification + rule-based materiality |

`operating_state` is DEGRADED whenever any configured source is
UNAVAILABLE that cycle, else TESTED — never self-promoted to
INTEGRATED/OPERATIONAL (same structural block as every other
institution in this federation: `external_attestation_ref` is never set
by this institution's own code).

## What News reports may include (mission section 22)

New events, updated events, contradictions, source-health changes,
emerging topics, cross-system implications, uncertainty,
evidence/provenance, resource use — all real fields on the generic
`InstitutionalReport`, populated only when this mission's real code
actually produced that content (e.g. no "emerging topics" trend
detector was built this mission, so that field is simply absent, not
fabricated).
