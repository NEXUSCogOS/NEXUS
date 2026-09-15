# SENTINEL F5.1 — PRE-MODIFICATION BASELINE
**Recorded:** 2026-08-28, before any F5.1 modification

## Repository state
- Sentinel repo HEAD: `c834dca7dc1d2f1dc1da2003c24e2bf25200a768` (branch `completion/final-shadow-stages`)
- NEXUS repo HEAD: `fe37b21a97813cde5b1abaa0d9f2e06b271950b3`
- Sentinel working tree: 24 untracked entries, all previously classified RETAIN_UNCOMMITTED_PENDING_EVIDENCE / GENERATED_ONLY in the F5 Phase 4 reconciliation (`decision/`, `learning/`, `portfolio/`, `risk/`, `bin/frontier-benchmark-*`, `reports/BACKUP_PRUNE_MANIFEST_20260814.md`, `.superpowers/sdd/2026-08-14-phase-9-ab/*`)

## File hashes (SHA-256)
- `frontier_pipeline.py`: `f2137793285be0f428906b0c31538dd4411a0d7fe283ef69b49bf5a72fc5efea`
- `decision/frontier_decision_engine.py`: `c5f669fd8f8db6ae69966dfb112267433391f747d58f71e2e16298ba187e70a3`
- `frontier_ingest.py`: `70f09c74f670f61b5319c3eff499ab7aba7de28b3fb37c2c5474a406e1a5a0ff`
- `financial_intelligence.db`: `512a0a779e8e85a666032942bbfb5440058645401fbe6f5e50d9700beae8deaa`

## Active scheduler configuration
| Job | Program |
|---|---|
| com.sentinel.doctor | `bin/sentinel-doctor --json`, `bin/sentinel-status --json` |
| com.sentinel.frontier | `python3 -X faulthandler -m sentinel.frontier_pipeline --stage all` |
| com.sentinel.ingest | `bin/run_ingest.sh` (→ `python3 -m sentinel.ingest --once`) |
| com.sentinel.shadowcycle | `python3 -X faulthandler bin/frontier-shadow-cycle` |

## Database state (read-only query, `financial_intelligence.db`)
| Table | Row count | Latest timestamp |
|---|---|---|
| prices_daily | 476,781 | 2026-08-27 (valid-date rows only; 689 rows excluded as malformed, see below) |
| frontier_decisions | 330 | 2026-08-14T00:03:27.544627+00:00 |
| frontier_market_regime | 1 | 2026-08-14T00:15:04.270065+00:00 |
| signals_unified | 60,564 | 2026-08-14T06:53:35.206141 |
| frontier_shadow_executions | 10 | — |

Note: `frontier_shadow_executions` count is 10 here vs. 9 reported in the F5 Phase 4 final report minutes earlier — attributable to the independently-scheduled `com.sentinel.shadowcycle` LaunchAgent running on its own timer in the background, not to any F5.1 action (none had been taken yet at time of this baseline capture).

## Execution safety state (baseline)
```
frontier_decisions:         DISTINCT(execution_mode, execution_allowed) = [('SHADOW', 0)]
frontier_shadow_executions: DISTINCT(execution_mode, execution_allowed) = [('SHADOW', 0)]
```
No non-SHADOW value present. This is the state F5.1 must preserve exactly.
