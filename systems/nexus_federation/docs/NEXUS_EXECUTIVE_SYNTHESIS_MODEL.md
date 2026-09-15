# NEXUS EXECUTIVE SYNTHESIS MODEL
**NEXUS Federation F6 — 2026-08-28**

Implemented in `synthesis/cross_domain_synthesis.py`. See
NEXUS_CROSS_DOMAIN_REASONING_MODEL.md for how a synthesis input is
produced; this document covers only the synthesis step itself.

## The ExecutiveSynthesis object

Never a concatenation of the two reports (mission section 12's explicit
prohibition). Every field is computed by a named function:

| Field | How it's computed |
|---|---|
| `supporting_findings` / `contradictory_findings` | Per-finding bucketing (`_bucket`) on the finding's LEADING epistemic tag only |
| `independent_corroboration` | Both institutions SUPPORT-bucketed AND their evidence_refs sets are disjoint (mission section 14: never double-count one originating fact as two) |
| `uncertainties` / `data_gaps` | Passed through verbatim from each report's own `uncertainty`/`limitations` fields |
| `temporal_mismatches` | Real date-arithmetic against the DAT.AI observation timestamp and each report's own staleness disclosures |
| `executive_conclusion_class` | A fixed decision table (below) -- never a learned/opaque score |
| `prohibited_actions` | A fixed, hardcoded list (see EXECUTIVE_RECOMMENDATION_POLICY.md) -- identical on every synthesis, never varies with the conclusion |

## The executive_conclusion_class decision table

Evaluated in this exact order (first match wins):

1. `partial` (an institution is missing) → `INSUFFICIENT_EVIDENCE`, conclusion explicitly says "withheld pending retry"
2. Contradiction present AND at least one SUPPORT bucket → `CONTRADICTORY_EVIDENCE`
3. Independent corroboration recorded → `SUPPORTED_CROSS_DOMAIN_INFERENCE`
4. Both institutions bucketed `INSUFFICIENT` → `INSUFFICIENT_EVIDENCE`
5. Support present, no contradiction → `PARTIALLY_SUPPORTED`
6. Support and contradiction both present → `MIXED_EVIDENCE`
7. Otherwise → `NO_MATERIAL_CROSS_DOMAIN_EFFECT_ESTABLISHED`

## Claim-class preservation

The bucketing (`_bucket()`) is used ONLY to select
`executive_conclusion_class` — the original institution-specific claim
class (`SOURCE_FACT`, `DERIVED_METRIC`, `MODEL_ESTIMATE`, etc.) is always
carried through verbatim into `supporting_findings`/
`contradictory_findings`/`uncertainties`. A reader of the synthesis
object can always see exactly which institution said what, in that
institution's own vocabulary.

**Bucketing matches only the LEADING tag** (text before the first
colon) of a finding string — a real defect (matching anywhere in the
text) was found and fixed during F6 construction; see
F6_SCIENTIFIC_EVALUATION.md for the concrete case that exposed it.

## Idempotent persistence

`executive_conclusion_class` and evidence are computed fresh on every
`synthesize()` call (cheap, pure, useful even on a would-be-duplicate
run), but the PERSISTED executive state event
(`state_event_log`, institution_id=`nexus`) is written only once per
distinct pair of input report_ids — see F6_REPRODUCIBILITY_PROTOCOL.md.
