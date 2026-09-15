# NEWS MATERIALITY MODEL
**NEXUS Federation F7 — 2026-08-28**

Implemented in `event_engine.py::assess_materiality()`. Deterministic,
disclosed factors only — no opaque AI score (mission section 18's
explicit prohibition).

## Factors

| Factor | Range | Rule |
|---|---|---|
| `source_quality` | 1–2 | 2 if any source is PRIMARY_OFFICIAL/GOVERNMENT/REGULATOR, else 1 |
| `event_type_score` | 0–2 | 2 for REGULATORY/M_AND_A/INFRASTRUCTURE/PLANNING/MACROECONOMIC, 1 for any other classified type, 0 for UNKNOWN |
| `resolved_entity_score` | 0–2 | `min(2, count of resolved entities)` |
| `geographic_scope_score` | 0–1 | 1 if geography is not UNKNOWN |
| `independent_corroboration_score` | 0–2 | `min(2, independent_source_count)` |
| `novelty_score` | 0–1 | 1 if novelty == NEW |
| `unresolved_entity_penalty` | 0 to −2 | `-min(2, count of unresolved entities)` |

`score = sum(all factors)`. Routing threshold: `MIN_MATERIALITY_FOR_ROUTING = 5` (`relevance/news_event_router.py`).

## Worked example (the real F7 event)

Samsung Bắc Ninh/Thái Nguyên export event:
```
source_quality=1 (MAINSTREAM_NEWS, not PRIMARY_OFFICIAL)
+ event_type_score=1 (SUPPLY_CHAIN, not in the high-materiality set)
+ resolved_entity_score=2 (2 locations resolved)
+ geographic_scope_score=1
+ independent_corroboration_score=1 (1 independent publisher)
+ novelty_score=1 (NEW)
+ unresolved_entity_penalty=-1 (Samsung itself unresolved)
= 6 (>= threshold 5 -> eligible for routing)
```

Negative control (durian pricing article):
```
event_type_score=0 (UNKNOWN -- no keyword matched)
+ resolved_entity_score=0 (zero entities extracted)
+ ... = 4 (< threshold 5 -> correctly not routed)
```

## Explicit limitation

Like NEXUS's own F6 attention model, this materiality score has not been
calibrated against any labeled dataset of real events and outcomes — it
is a fixed, inspectable rule set appropriate to F7's initial
commissioning, not a validated predictor of true real-world
significance.
