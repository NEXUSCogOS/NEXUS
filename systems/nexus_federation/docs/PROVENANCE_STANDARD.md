# Provenance Standard

**Status**: GROUNDED, with an explicit open gap noted below.

## What NEXUS Federation F1 does with provenance_refs

`evidence/resolver.py::looks_like_commit_reference()` extracts a hex
substring matching a plausible git commit hash (7-40 characters) from a
`provenance_ref` string, when one is present. Example, from a real DAT.AI
report: `"NEXUS_LOCAL donor commit eb9ed1c (systems/dat_ai)"` →
`"eb9ed1c"`.

## What this does NOT do (stated, not hidden)

It does not verify that hash against any specific repository. DAT.AI's
`provenance_refs` are prose describing donor lineage (established in the
prior DAT.AI Phase A+B/C missions via direct `git log`/`git cat-file`
inspection of the actual donor repository) — a correct, real, previously-verified
claim, but the *format* NEXUS receives it in (a sentence, not a structured
`{repo, commit}` pair) does not carry enough structure for NEXUS to
independently re-verify it against a specific repo without a hardcoded
assumption about which repo every DAT.AI provenance_ref refers to. Adding
that assumption would be exactly the kind of "inferring more than the
evidence supports" this standard exists to prevent.

## The honest current standard

1. A `provenance_ref` is stored verbatim, exactly as reported.
2. If a commit-hash-shaped substring is present, it is extracted and
   recorded as a `candidate_commit_reference` — informational, not a pass/
   fail verification result.
3. NEXUS does not claim to have verified institutional provenance beyond
   what the evidence-resolution mechanism (`EVIDENCE_MODEL.md`) already
   proves for file-based `evidence_refs`.

## Recommended future work (not attempted this phase)

A structured provenance schema — `{repo_path, commit_hash, file_path}` —
would let NEXUS run `git cat-file -e <hash>` against a named repository
directly. This requires a coordinated change to the reporting institution's
contract (DAT.AI's `provenance_refs: list[str]` would need to become
`list[ProvenanceReference]`), out of scope for F1's "consume DAT.AI's
existing contract directly, do not modify it" boundary.
