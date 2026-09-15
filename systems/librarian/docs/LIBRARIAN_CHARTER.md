# LIBRARIAN CHARTER
**NEXUS Federation F3 — 2026-08-27**

## What Librarian is

Librarian is NEXUS's research-support institution: it ingests, stores,
and retrieves a corpus of documents, and answers bounded research
requests from other institutions (currently only NEXUS itself, via a
federation delegation) with real, evidenced retrieval results.

## What Librarian is NOT (yet)

Librarian is not a literature-review system, a citation graph, a
hypothesis tracker, or a paper-generation pipeline. Prior donor material
(`/Volumes/NEXUS/NEXUS_LOCAL/systems/librarian`) used those names
extensively in documentation and directory scaffolding, but none of that
code was ever implemented — see `LIBRARIAN_DONOR_FORENSIC_REPORT.md` and
`LIBRARIAN_COMPONENT_RECOVERY_MATRIX.md` for the full forensic accounting.
This charter describes what actually exists, canonically, today.

## Core rule (inherited from the donor, honored in the recovery)

The donor's own stated principle — *"No research claim is treated as
established solely because it appears in a document, model response,
repository artifact or implementation. Every claim must link to evidence,
provenance, confidence, limitations and review status"* — is enforced
structurally here via the shared NEXUS Federation contract
(`contracts.generic`), not merely stated. A finding without an
`evidence_ref` cannot be constructed (pydantic validator).

## What is real, canonically, as of F3

1. **Corpus ingestion and storage** (`ingestion/`, `corpus/`) — recovered,
   tested (22/22), unchanged logic from the `librarian_rag` donor.
2. **Lexical retrieval** (`retrieval/`) — new this mission, minimal and
   honestly scoped: substring matching only, no semantic ranking.
3. **Institutional reporting** (`reporting/`) — new this mission, built
   on NEXUS Federation's generic contract, never a bespoke parser.
4. **Bounded research execution** (`runtime/`) — new this mission: answers
   one research question per mission, real retrieval, real evidence,
   honest `INSUFFICIENT_EVIDENCE` when the corpus doesn't support a claim.
5. **Delegation delivery** (`runtime/delegation_inbox.py`) — new this
   mission: persistent, idempotent, auditable, restart-safe, using the
   shared federation store — never a direct Python call across the
   institutional boundary.

See `LIBRARIAN_LIMITATIONS.md` for the complete, explicit list of what is
NOT commissioned and why.
