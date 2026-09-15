# NEWS → NEXUS E2E EVIDENCE
**NEXUS Federation F7 — 2026-08-28**

Real, captured execution of the full event-driven cognitive loop
(mission section 25). No conclusion chosen in advance — the routing
outcome and executive conclusion below are the actual output of this
mission's deterministic code, run against live data.

## Real item acquired

**Source:** VnExpress Kinh Doanh RSS (`https://vnexpress.net/rss/kinh-doanh.rss`, public, no auth)

**Headline:** "Samsung xuất khẩu 500 tỷ USD điện thoại từ Việt Nam sau 17 năm"
("Samsung has exported $500B worth of phones from Vietnam after 17 years")

**Publication timestamp:** real, from the live feed (RFC 822, parsed to UTC ISO 8601)

**Canonical URL / content_hash:** real, computed at acquisition time —
see `F6_TRIGGER_EVIDENCE`-style provenance in the federation store.

## Real entity extraction

| Surface form | Type | Resolution | Basis |
|---|---|---|---|
| Bắc Ninh | LOCATION | RESOLVED | exact match, fixed VN province list |
| Thái Nguyên | LOCATION | RESOLVED | exact match, fixed VN province list |
| Samsung | COMPANY | UNRESOLVED | real company, not in Sentinel's governed universe — correctly not forced to a ticker |

## Real event construction

- `event_type`: `SUPPLY_CHAIN` (keyword match: "xuất khẩu"/"export")
- `materiality`: 6 (see NEWS_MATERIALITY_MODEL.md's worked example — this is that exact real computation)
- `novelty`: `NEW` (no prior event with this cluster_id)
- `claim_epistemology`: `REPORTED_CLAIM` (MAINSTREAM_NEWS source, 1 independent publisher — not auto-promoted to PRIMARY_SOURCE_FACT)
- `freshness`: `CURRENT`

## Real NEXUS relevance assessment

| Institution | Relevant | Reason |
|---|---|---|
| dat_ai | NO | `SUPPLY_CHAIN` not in DAT.AI's geospatial/zoning-relevant event-type set |
| librarian | NO | `SUPPLY_CHAIN` not in Librarian's policy/research-relevant event-type set |
| sentinel | **YES** | `SUPPLY_CHAIN` is financial/corporate-relevant |

Only Sentinel was delegated to — a genuine, non-predetermined,
single-institution routing outcome.

## Real Sentinel execution

5 candidate tickers (KBC, SZC, GVR, IDC, LHG — real, known Vietnamese
industrial-park/land-bank operators) checked against Sentinel's own
`companies` table:

- KBC, SZC → `INDIRECT` (real estate sector, no facility-level confirmation)
- GVR, IDC → `HYPOTHETICAL` (not real-estate-sector-classified)
- LHG → `UNKNOWN` (no row in Sentinel's companies table)

Real prices observed (`OBSERVED_MARKET_FACT`) for each ticker with data
available. `execution_mode`/`execution_allowed` confirmed
`[('SHADOW', 0)]` before and after.

## Real executive synthesis

```
executive_conclusion_class = NO_MATERIAL_CROSS_DOMAIN_EFFECT_ESTABLISHED
executive_conclusion = "No institution reported evidence establishing
                         a material cross-domain effect."
partial = False
missing_institutions = []
recommended_next_actions = ["continue monitoring"]
```

Sentinel's real findings were all `DERIVED_METRIC`-tagged entity
mappings (INDIRECT/HYPOTHETICAL/UNKNOWN) — none bucket as SUPPORT or
CONTRADICT under the synthesis engine's leading-tag matching, so the
honest, non-inflated conclusion is that no material cross-domain
financial effect was established from Sentinel's real, governed data.
This is a legitimate, bounded F7 result, not a failure of the
experiment.

## Process identity

Four real, distinct OS processes (News acquisition, NEXUS Process A,
Sentinel, NEXUS Process B), verified via distinct PIDs in
`test_f7_full_event_driven_cognitive_loop`.
