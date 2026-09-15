# LIBRARIAN INSTITUTIONAL CONTRACT
**NEXUS Federation F3 — 2026-08-27**

## No Librarian-specific federation parser exists

Per the mission's explicit instruction, Librarian does NOT own a bespoke
`institutional.contract`-style module (the way DAT.AI does). Instead,
`reporting/reporter.py` builds reports directly against NEXUS Federation's
own shared, institution-agnostic contract:
`nexus_federation/contracts/generic.py` (new this mission).

This module lives in `nexus_federation`, not in `dat_ai` or `librarian`,
specifically so a THIRD institution (News, YouTube, etc.) can reuse it
too, rather than each institution reinventing the same validation rules.

## Registration

```python
# ingress/contract_registry.py
"librarian": ContractRegistration(
    validate_fn=validate_generic_report,
    known_schema_versions=frozenset({"1.0.0"}),
)
```

Adding Librarian required ONE registry entry — zero changes to
`ingress/validator.py`'s dispatch logic, `kernel.py`, or any
state/evidence/relevance module. Proven:
`tests/contract/test_generic_contract_compat.py`.

## Real capability statuses Librarian reports (see reporting/reporter.py)

| Capability | Lifecycle | Basis |
|---|---|---|
| `corpus_ingestion` | INTEGRATED | 22/22 recovered tests pass |
| `corpus_storage` | INTEGRATED | real DB present, 7/7 tests pass |
| `corpus_retrieval` | TESTED | new lexical search, tested this mission |
| `literature_review` | NOT_COMMISSIONED | no code exists |
| `citation_academic_metadata` | NOT_COMMISSIONED | no metadata ever populated |
| `hypothesis_project_paper_generation` | NOT_COMMISSIONED | only an unfilled-template generator existed, archived |

Librarian's `operating_state` is derived (never self-asserted) from its
core capability (`corpus_retrieval`)'s lifecycle — see
`reporting/reporter.py::_derive_operating_state`. `OPERATIONAL` requires
`external_attestation_ref`, which no code path here ever sets — Librarian
structurally cannot self-promote to `OPERATIONAL`, exactly mirroring
DAT.AI's own contract discipline.

## Typical outputs (mission section 14) — what's real vs. not yet

| Output | Status |
|---|---|
| Research findings | ✅ real (literal retrieved excerpts) |
| Literature evidence | ✅ real (`evidence_refs`/`provenance_refs` per finding) |
| Source-quality state | ✅ real (`SOURCE_HIERARCHY.md` classification) |
| Contradictions | Handled at NEXUS Federation level, not Librarian-internal |
| Research gaps | Expressed as `INSUFFICIENT_EVIDENCE` |
| Hypotheses | NOT_COMMISSIONED |
| Project status | NOT_COMMISSIONED |
| Paper status | NOT_COMMISSIONED |
| Corpus health | ✅ real (`LIBRARIAN_CORPUS_AUDIT.md`-style counts, available via `corpus.database` queries) |
| Research requests | ✅ real (this is the delegation-receiving direction, not outbound) |
| Cross-system implications | Field exists in the shared contract; unpopulated absent a real cross-system implication to report |
