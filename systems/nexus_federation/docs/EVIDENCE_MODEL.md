# Evidence Model

**Status**: GROUNDED. `evidence/resolver.py`.

## The core principle

**An `evidence_ref` string is a claim, not proof.** This module is the
only place that claim is checked against a real filesystem.

## What is checked

1. **Syntactic validity** — non-empty, no null bytes, bounded length.
2. **Existence** — resolved against named, explicit search roots
   (`dat_ai_canonical`, `dat_ai_canonical_docs`,
   `engineering_studio_audit_trail`), first match wins, the winning root is
   recorded.
3. **Integrity baseline + drift** — on first resolution, a SHA256 is
   computed and persisted (`persistence.db::evidence_baseline`, immutable
   once set). Every subsequent resolution of the *same* `(institution, ref)`
   pair is compared against that original baseline; a hash mismatch is
   surfaced as drift.

## Honest limitation, stated rather than hidden

DAT.AI's contract carries `evidence_refs` as **plain strings with no
accompanying expected hash**. This means first-resolution "integrity
verification" is not possible in the sense of checking against an
independently-supplied expected value — there is nothing to compare
against yet. What this module actually does is establish the baseline
itself and detect *change from that baseline going forward* — real
integrity monitoring, honestly scoped to what the input data supports, not
overclaimed as first-contact verification.

## Provenance refs

`provenance_refs` are often prose with an embedded commit hash (e.g.
`"NEXUS_LOCAL donor commit eb9ed1c (systems/dat_ai)"`) rather than a clean
identifier. `looks_like_commit_reference()` extracts the hash-like
substring when present. This is a **partial** check: it identifies a
candidate reference, it does not verify that hash exists in any specific
repository (no standard field indicates which repo a given provenance_ref
belongs to). See `PROVENANCE_STANDARD.md`.

## Verified

Real resolution against real canonical DAT.AI files
(`tests/evidence/test_evidence_resolver.py`), real drift detection via a
mutated temp file (simulating corruption), and a full end-to-end run
against a live DAT.AI report where both `zoning_api`'s and `valuation`'s
`evidence_refs` resolved successfully on the first attempt.
