# LIBRARIAN LIMITATIONS
**NEXUS Federation F3 — 2026-08-27**

This document consolidates every capability the mission's target
architecture names that Librarian does NOT have, rather than producing
one thin, near-empty document per missing capability (which the mission
explicitly warns against: "do not generate unsupported target docs merely
to increase document count").

## NOT_COMMISSIONED capabilities (no code exists; not fabricated)

| Capability | Target doc this would have been | Why it doesn't exist |
|---|---|---|
| Citation graph | `CITATION_GRAPH_SPEC.md` | No citation metadata (author/DOI/journal) is ever captured — see `ACADEMIC_PROVENANCE_STANDARD.md` |
| Literature review | `LITERATURE_REVIEW_METHOD.md` | No synthesis/review code exists anywhere in the donor |
| Systematic review support | `SYSTEMATIC_REVIEW_PROTOCOL.md` | `.gitkeep`-only scaffolding in the donor, no code |
| Evidence synthesis | `EVIDENCE_SYNTHESIS_METHOD.md` | No code exists |
| Contradictory evidence handling (within Librarian itself) | `CONTRADICTORY_EVIDENCE_PROTOCOL.md` | Handled at the NEXUS Federation level instead (kernel.py's cross-cycle contradiction detection, institution-agnostic) — no Librarian-internal mechanism exists or is needed |
| Project creation | `PROJECT_CREATION_PROTOCOL.md` | Donor only had an unfilled-template generator script (`ingest.py`'s `add_resource()`), archived not recovered |
| Paper generation | `PAPER_CREATION_PIPELINE.md` | Same template mechanism as project creation; no generation logic |
| Reproducibility standard (beyond ingestion) | `RESEARCH_REPRODUCIBILITY_STANDARD.md` | Ingestion IS reproducible (parser/chunker versioning); there is no synthesis/finding-generation step yet whose reproducibility would need its own standard |

## Real, disclosed weaknesses in what DOES exist

1. **Lexical search false positives on generic terms.** A single common
   word (e.g. "index") can match unrelated content. Mitigated via
   `min_matched_terms` (default 2 for real missions) — see
   `retrieval/lexical_search.py` and `LIBRARIAN_CANONICAL_TEST_BASELINE.md`.
2. **Corpus content is not academic literature.** All 93 real ingested
   sources are Librarian's own operational documentation — see
   `LIBRARIAN_CORPUS_AUDIT.md`. A real academic research question will
   likely (correctly) return `INSUFFICIENT_EVIDENCE`.
3. **Stale evidence_refs.** Real corpus sources' `source_uri` point at
   `~/Librarian`, which no longer exists on this machine — NEXUS's
   evidence resolver correctly reports these `MISSING`, never fabricated
   as verified.
4. **`query_history` is unpopulated.** The schema exists; no code path
   writes to it yet (retrieval was only just built this mission).
5. **No source-quality classifier exists** beyond the manual audit in
   `LIBRARIAN_CORPUS_AUDIT.md`/`SOURCE_HIERARCHY.md`.
6. **`corpus/database.py`'s `DatabaseConnectionPool` does not actually
   pool connections** (opens a fresh one per call) — documented honestly
   in its own docstring, kept for import compatibility with recovered
   callers.
