# Data Source Registry (DAT.AI)

**Status**: GROUNDED — lists only sources confirmed by code inspection this phase and the prior donor forensic mission.

| Source | Type | Status in canonical | Credentials | Licensing |
|---|---|---|---|---|
| Vietnamese government planning-database exports (Dong Nai) | Zoning/land-use polygons | Recovered — ingestion pipeline + ORM model tested | None required (file-based ingestion) | **UNKNOWN — not established this phase or prior.** See `DATAI_LIMITATIONS.md`. |
| Copernicus Data Space Ecosystem (CDSE) | Sentinel-2 satellite imagery (STAC + S3/OAuth2) | Schema present (`SatelliteProduct` etc.), acquisition code NOT recovered | **Confirmed NOT_FOUND** anywhere in this estate (Phase A+B credential search: env, filesystem, LaunchAgents, Keychain) | N/A — not currently used |
| Planet Labs | Optional high-res validation imagery | Schema present (`PlanetImagery`), acquisition code NOT recovered | **Confirmed NOT_FOUND** | N/A |
| batdongsan.com.vn, chotot.com | Vietnamese property listing scrapers | NOT recovered (part of `worker/source_*.py`, MODERNIZE-classified in the prior donor audit) | Public scraping, no credentials found | Not established |

## What this registry does not yet cover

Valuation data sources (the donor's `source/valuation_engine.py` reads from
a hardcoded `/tmp/real_listings.json`) — not part of canonical recovery this
phase; see `DATAI_PHASE_C_RECOVERY_REPORT.md` for the valuation assessment.

## Data licensing — explicit open item

**No licensing determination has been made for the Vietnamese government
zoning data.** This was flagged in the prior donor-forensic mission
(`DATAI_DATA_ASSET_REGISTER.md`) and remains unresolved. It should be
confirmed before any production ingestion of new zoning data or any
redistribution of the existing 12KB test fixture beyond its current use as
a pytest fixture for the ingestion-pipeline tests recovered this phase.
