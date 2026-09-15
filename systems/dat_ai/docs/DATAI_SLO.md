# DAT.AI Service Level Objectives

**Status**: TARGET_DESIGN_ONLY for numeric SLOs — DAT.AI is not deployed anywhere with production traffic, so no real latency/availability measurements exist yet. What follows are the *readiness signals* that already exist and are real, plus explicitly-marked target numbers for later.

## Real, currently-measured signals (not targets — these are live checks)

`/readiness` reports, per request, computed at request time:
- `database` — healthy/unhealthy (real connection check)
- `postgis` — healthy/unhealthy + version string (real query)
- `migrations` — healthy/unhealthy + exact missing-version list (real query against `schema_migrations`)
- `classifier` — healthy/not_promoted/unhealthy (real checkpoint audit)
- `satellite_ingestion` — disabled/unconfigured/healthy (real config check)
- `configuration` — healthy/unhealthy + problem count (real validation)

These are genuine evidence-derived states today, not a future target.

## Numeric targets (TARGET_DESIGN_ONLY — not yet measured against any real deployment)

| Metric | Target | Status |
|---|---|---|
| `/health` p99 latency | < 50ms | NOT_YET_MEASURED — no deployment exists |
| `/readiness` p99 latency | < 500ms (includes DB round-trip) | NOT_YET_MEASURED |
| `/zoning/zones` p99 latency (empty result) | < 200ms | NOT_YET_MEASURED |
| Availability | Not defined | Cannot define an availability target for a service with no deployment |

## Why no numeric SLOs are asserted as current fact

Per the mission's explicit instruction not to fill documentation gaps with
speculative prose: DAT.AI has never run outside disposable test instances.
Any specific uptime/latency percentage would be invented, not measured.
This document will be updated with real targets once DAT.AI has a real
deployment environment (see `DATAI_PHASE_D_ENTRY_CRITERIA.md`).
