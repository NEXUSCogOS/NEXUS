# SCIENTIFIC RESEARCH ARCHITECTURE
**NEXUS Federation F3 — 2026-08-27**

## Real component/data-flow (derived from executable code, not README claims)

```
corpus roots (.md/.txt files)
        │  ingestion/discovery.py (walk, classify, hash)
        ▼
ingestion/normalize.py + chunk_text (deterministic normalize/chunk)
        │
        ▼
ingestion/pipeline.py (dedup: source-level + chunk-level; transactional persist)
        │                                   │
        ▼                                   ▼
corpus/database.py (SQLite:              corpus/json_store.py
sources, documents,                      (document text, sharded
chunk_map, ingestion_log)                by source, content-hashed)
        │
        ▼
retrieval/lexical_search.py (substring match against real stored text)
        │
        ▼
runtime/research_executor.py (bounded mission: real findings OR
                               INSUFFICIENT_EVIDENCE)
        │
        ▼
reporting/reporter.py + runtime/research_executor.py build an
InstitutionalReport via nexus_federation.contracts.generic
        │
        ▼
runtime/delegation_inbox.py (claims delegations from the shared
federation store; the ONLY coupling to NEXUS)
        │
        ▼
NEXUS Federation kernel.ingest_report() (separate process/institution)
```

## Entrypoints

- `ingestion/run_ingest.py` — CLI, manual/scheduled corpus ingestion.
- `runtime/research_executor.execute_research_mission()` — the one
  function that answers a bounded research question.
- `runtime/delegation_inbox.poll_and_execute()` — the one function that
  claims and executes pending NEXUS delegations.

## External dependencies

None. Pure Python stdlib throughout (confirmed by import audit in
`LIBRARIAN_DONOR_FORENSIC_REPORT.md`) — no embedding model, no vector
database, no LLM call, no network call anywhere in this institution's code.

## What does NOT exist (see LIBRARIAN_LIMITATIONS.md for the full list)

Source classification, citation handling, evidence synthesis, literature
review, research-gap detection, hypothesis generation, project/paper
creation. No component diagram is drawn for these because there is no
component to diagram — drawing one would misrepresent the donor.
