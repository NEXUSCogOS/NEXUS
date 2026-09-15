# Engineering Studio Takeover — PIONEER/Librarian

Canonical root: `${NEXUS_ROOT}/systems/librarian`

Comparison baseline: `pioneer/ENGINEERING_STUDIO_BASELINE.json`

## Mandatory execution order

1. Run `python3 pioneer/optimize_resources.py`.
2. Run `python3 pioneer/audit_pioneer.py`.
3. Run `python3 -m pytest -q`.
4. Proceed only when the optimizer is `PASS`, the audit has no false control, and the full suite passes.
5. Compare hashes, counts, states, findings, and recommendations against the baseline. Classify every difference as `IMPROVEMENT`, `REGRESSION`, `EXPECTED_GROWTH`, or `UNVERIFIED`; do not silently accept drift.

## Safety boundaries

- Never rewrite raw evidence. Place repairs and transformations beside it with hashes and lineage.
- Treat volume, archive, and iCloud research trees as reference-only unless a reviewed promotion changes the canonical registry.
- Never promote journal observations directly into runtime changes. Engineering feedback remains pending until reviewed.
- Do not publish or describe experimental claims as established while experiments remain blocked or replication is absent.
- Do not infer citation edges. Every edge requires explicit evidence and a verification state.

## Current scientific blockers

- Six preregistered experiments are blocked and have no final verdict.
- External corroboration is partial.
- The academic corpus is small, preprint-heavy, and only partially verified.
- The citation graph has no verified edges.
- Project and white papers remain blocked by evidence gates.

## Rollback and diagnosis

Pre-optimization database copies and hashes are under `pioneer/backups/2026-08-31-pre-resource-optimization/`. Optimization is additive: indexes, an FTS selection layer, inventories, and reports. Search retains the original deterministic lexical scorer and must produce equivalent result identities.
