# Federation Failure Model

**Status**: GROUNDED. All 15 scenarios below are individually tested in `tests/failure/test_failure_modes.py` (numbered to match exactly) and pass.

| # | Scenario | Handling | Test |
|---|---|---|---|
| 1 | Valid DAT.AI report | Accepted, registered | `test_01_valid_dat_ai_report` |
| 2 | Malformed report | Fails closed, `ValidationError` surfaced as rejection reason | `test_02_malformed_report_fails_closed` |
| 3 | Unknown schema version | Rejected explicitly, distinct from a generic validation failure | `test_03_unknown_schema_version_rejected` |
| 4 | Missing evidence | Report still accepted (it's schema-valid); the specific capability's `executive_state_class` degrades to `UNKNOWN` | `test_04_missing_evidence_degrades_claim_not_silently_accepted` |
| 5 | Corrupted evidence | Detected via hash-baseline drift on re-resolution | `test_05_corrupted_evidence_detected_via_hash_drift` |
| 6 | Stale report | Accepted, `executive_state_class=STALE` on every capability | `test_06_stale_report` |
| 7 | Out-of-order report | Rejected; prior newer accepted state provably untouched | `test_07_out_of_order_report` |
| 8 | Duplicate cycle | Accepted idempotently, no new registry churn, no new delegation | `test_08_duplicate_cycle` |
| 9 | PostGIS unavailable | DAT.AI honestly reports it; NEXUS registers `maturity=UNAVAILABLE` | `test_09_postgis_unavailable_reported_not_silently_ignored` |
| 10 | External storage unavailable | DAT.AI reports it; NEXUS registers `maturity=DEGRADED` | `test_10_external_storage_unavailable_reported_as_degraded` |
| 11 | Satellite credentials unavailable | Preserved verbatim as `EXTERNAL_DEPENDENCY_UNAVAILABLE`, not collapsed to a generic failure | `test_11_satellite_credentials_unavailable_reported_as_external_dependency_unavailable` |
| 12 | Valuation NOT_COMMISSIONED | Preserved verbatim, never coerced toward `OPERATIONAL` | `test_12_valuation_not_commissioned_preserved_verbatim` |
| 13 | Untrained classifier | Preserved as `IMPLEMENTED` with confidence 0.0; never `EMPIRICALLY_VALIDATED`/`OPERATIONAL` | `test_13_untrained_classifier_never_reported_as_validated` |
| 14 | Contradictory successive reports | Flagged `CONTRADICTORY`, not silently overwritten | `test_14_contradictory_successive_reports` |
| 15 | NEXUS restart between reports | New `FederationKernel`/`FederationStore` instances, same SQLite file, see identical prior state | `test_15_restart_between_reports` (+ full dedicated suite in `tests/restart/`) |

## What "handling" means precisely for each outcome

- **Rejected** (#2, #3, #7): the report is logged (in `report_log`, for
  observability) but the registry is untouched.
- **Accepted-but-degraded** (#4, #6, #9, #10): the report passes schema and
  temporal checks, the registry IS updated, but the specific problem is
  visible in the resulting state (`executive_state_class`, `maturity`) —
  never silently smoothed over.
- **Accepted-and-preserved** (#8, #11, #12, #13): the institution's own
  honest self-report is trusted and stored with full granularity, exactly
  as DAT.AI's own contract already guarantees at its layer.
- **Flagged, not resolved** (#14): NEXUS does not attempt to decide which
  of two contradictory reports is "right" — it marks the state
  `CONTRADICTORY` and leaves resolution to a future, more capable
  executive layer (or a human).
- **Survived** (#15): nothing durable was ever held only in process
  memory.
