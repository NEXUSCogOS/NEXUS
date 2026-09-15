# NEXUS ATTENTION ROUTING MODEL
**NEXUS Federation F6 — 2026-08-28**

Implemented in `relevance/cross_domain_router.py::assess_attention()`.
Per mission section 24: "Use transparent deterministic scoring/rules
initially. Do not introduce opaque LLM 'importance' scores without
calibration."

## The score

A literal sum of eight named, bounded factors — fully reproducible by
hand from the trigger's own fields:

| Factor | Range | Rule |
|---|---|---|
| `evidence_quality_score` | 0–2 | 2 if a government/authoritative source_url is present, 1 if any source_url, 0 otherwise |
| `materiality_score` | 0–2 | Bucketed from `trigger.materiality`: >0.6 → 2, 0.3–0.6 → 1, else 0 |
| `geographic_scope_score` | 0–1 | 1 if the geography string names a specific place (contains a comma), not just a country/region |
| `cross_domain_relevance_score` | 0–2 | Count of institutions found relevant (0, 1, or 2) |
| `novelty_score` | always 1 | No prior-trigger deduplication corpus exists in this harness to check novelty against — reported as 1, not fabricated as 0 (see limitation below) |
| `time_sensitivity_score` | 0–1 | 1 only if `trigger.freshness == "CURRENT"` |
| `institutional_coverage_score` | 0–1 | 1 if ≥2 institutions were evaluated |
| `uncertainty_penalty` | 0 to −2 | −1 per limitation/uncertainty item beyond the first 2, capped at −2 |

`total_score = sum(all factors)`. `requires_attention = total_score >= ATTENTION_THRESHOLD` (4).

## Worked example (the real F6 trigger)

```
evidence_quality=1 (source is a Google Drive link, not the government
                     portal URL directly cited on this specific trigger)
+ materiality=2 (0.65)
+ geographic_scope=1 ("Long Thanh district, Dong Nai province, Vietnam")
+ cross_domain_relevance=2 (both institutions relevant)
+ novelty=1
+ time_sensitivity=0 (freshness=STALE_BUT_USABLE_AS_HISTORICAL_CONTEXT)
+ institutional_coverage=1
+ uncertainty_penalty=-2 (5 limitation/uncertainty items -> capped)
= 6 (>= threshold 4 -> requires_attention=True)
```

## Explicit limitation

`novelty_score` is hardcoded to 1 because this harness has no
persistent "have I seen a materially similar trigger before" corpus to
check against. This is disclosed here rather than either (a) silently
omitting novelty from the score, or (b) fabricating a 0 that would imply
a check was performed. A real novelty check requires a trigger-history
store, out of this mission's scope.

## Not used

No LLM call, no learned weight, no calibration dataset. Every factor is
a fixed rule over the trigger's own declared fields. This is the
"initially" state per mission section 24 — a future mission may
calibrate `ATTENTION_THRESHOLD` or the factor weights against a labeled
dataset of triggers, but that has not happened and is not claimed here.
