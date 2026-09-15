# YOUTUBE INSTITUTIONAL CONTRACT
**NEXUS Federation F8 — 2026-08-28**

## Registration

```
institution_id       = youtube_production
institution_type     = PRODUCTION
domain               = MEDIA_PRODUCTION
authority_ceiling     = GENERATE_INTERNAL
publication_authority = NOT_GRANTED
contract             = contracts.generic (SAME generic federation contract
                        DAT.AI/Librarian/Sentinel/News Intelligence use --
                        no YouTube-specific NEXUS parser)
```

Registered in `ingress/contract_registry.py` (`_REGISTRY` and
`bootstrap_federation_registry()`) and `kernel.py::INSTITUTION_TYPES`
(`"youtube_production": "media_production"`), the same additive pattern
every prior institution used.

## What YouTube Production owns

Editorial transformation of already-established evidence into a script;
script construction with explicit claim-class separation; media
production (voice, visual, render, thumbnail, metadata); production-side
quality control (factual integrity, citation coverage, rights state,
render completeness).

## What YouTube Production does NOT own

World-event truth (News Intelligence), academic/policy truth (Librarian),
financial truth (Sentinel), geospatial truth (DAT.AI), or cross-domain
relevance/materiality determination (NEXUS itself). YouTube Production
never originates a factual premise -- every claim in a script traces to
an `evidence_id` in an `EvidencePack` built from another institution's
already-accepted report, never invented here.

## Authority

This is the first NEXUS Federation mission whose institution needs more
than `ANALYSE`: producing a script and a rendered video is generating a
durable internal artifact. `authority/model.py::MAX_GRANTABLE_AUTHORITY_
THIS_PHASE` was deliberately, visibly raised from `ANALYSE` to
`GENERATE_INTERNAL` for exactly this reason (see that module's own
comment). `EXTERNAL_ACTION` and `HIGH_CONSEQUENCE_ACTION` -- the levels
publication would require -- remain unreachable through the same
structural mechanism (`DelegationProposal`'s `_authority_never_exceeds_
phase_ceiling` validator). See YOUTUBE_PUBLICATION_BOUNDARY_TEST.md for
the mandatory proof.

## Allowed vs. not allowed

| ALLOWED | NOT ALLOWED (this mission) |
|---|---|
| Consume a research package / evidence pack | Publish to YouTube |
| Generate script, voice, visuals | Schedule a publication |
| Edit, render, generate thumbnail/metadata | Post externally on any platform |
| Internal QC | Use production credentials for anything external |

## Terminal state

Every production mission this institution completes ends at
`READY_FOR_PUBLICATION_AUTHORIZATION` -- never `PUBLISHED`. A separate,
future, explicit authorization step (not part of this mission) would be
required before any upload could even be attempted, and even then would
use different code than anything in this package (see
YOUTUBE_F8_FORENSIC_REPORT.md's account of the pre-existing, separate,
never-authenticated `youtube_uploader.py`, which this package never
imports).

## Component ownership inside an InstitutionalReport

`evidence_pack`, `script`, `fact_check`, `voice`, `visuals`, `rights`,
`editing`, `render`, `thumbnail`, `metadata`, `publication` -- see
`institutional_report.py::build_youtube_report()`. `publication` is
always reported `NOT_COMMISSIONED`, every real run, structurally --
there is no code path in this package that could set it to anything
else.
