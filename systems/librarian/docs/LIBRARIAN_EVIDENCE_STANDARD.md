# LIBRARIAN EVIDENCE STANDARD
**NEXUS Federation F3 — 2026-08-27**

## Research epistemology (mission section 9)

Every Librarian research output distinguishes:

| Category | How Librarian expresses it |
|---|---|
| SOURCE FACT | A literal, quoted excerpt from a real stored chunk, with `source_uri` |
| DERIVED SYNTHESIS | **Not produced.** `literature_review`/`evidence_synthesis` are `NOT_COMMISSIONED` — see `LIBRARIAN_LIMITATIONS.md`. Librarian never paraphrases or interprets. |
| INFERENCE | **Not produced.** No inference mechanism exists. |
| HYPOTHESIS | **Not produced.** `hypothesis_project_paper_generation` is `NOT_COMMISSIONED`. |
| CONTRADICTION | Handled at the NEXUS Federation level (`kernel.py`'s contradiction detection across Librarian's own successive reports), not by Librarian internally. |
| OPEN QUESTION | Expressed as the literal `INSUFFICIENT_EVIDENCE` finding when retrieval finds nothing relevant. |
| UNVERIFIED CLAIM | Every finding's `evidence_ref` is subject to NEXUS's own evidence resolver, which may report it `MISSING` (e.g. a stale `~/Librarian` path) — Librarian never asserts a claim is verified beyond "this exact text exists in the corpus." |

## Every substantive finding carries

- `evidence_refs`: the real `source_uri` (or `source_id` fallback) of the
  matched chunk.
- `provenance_refs`: `source_id`, `chunk_index`, `content_hash` — enough
  to independently re-locate and re-verify the exact chunk.
- `uncertainty`/`limitations`: stated explicitly on every report (see
  `reporting/reporter.py` and `runtime/research_executor.py`) — e.g. "this
  is a literal excerpt, not synthesis" and "evidence_refs may point at
  paths that no longer exist on this machine."

## Anti-fabrication audit result (mission section 8)

No random/scaffolded research output, no fake citation, no fabricated
DOI, no invented paper metadata, no simulated experiment result, no fixed
confidence score outside the `Confidence.basis`-required discipline, no
self-certifying quality status, no placeholder evidence, no fallback fake
summary was found in the RECOVERED code (`librarian_rag`). The donor
SCAFFOLD tree (`systems/librarian`) DID contain the self-certifying
pattern (`SYSTEM_CERTIFIED_FINAL.txt` etc.) — documented and archived, not
recovered — see `LIBRARIAN_DONOR_FORENSIC_REPORT.md` section 2 and
`LIBRARIAN_COMPONENT_RECOVERY_MATRIX.md`.

`reporting/reporter.py`'s `QueryHistory.model_used` default was itself a
hardcoded, never-actually-used model name (`'llama2-uncensored:7b'`) —
classified and fixed as exactly this kind of unsupported fixed value; see
`corpus/schema.py`'s module docstring.
