# Migration 001 — Retirement Note

**Retired**: 2026-08-27, during DAT.AI Phase C canonical recovery.

`001_satellite_tables.sql` predates the SQLAlchemy ORM models
(`app/models/satellite.py`). It is fully superseded by `Base.metadata.create_all()`,
which the live application uses to bootstrap its schema, and additionally
references a `valuation_history` table that does not exist anywhere in the
current schema — so even an idempotency fix (`CREATE TABLE IF NOT EXISTS`)
would not make it safe to run against a current database.

**Evidence**: see `DATAI_PHASE_AB_VERIFICATION_REPORT.md` §2 and
`DATAI_POSTGIS_SCHEMA_EVIDENCE.md` (prior mission) for the original diagnosis,
and `DATAI_DEFECT_REPAIR_EVIDENCE.md` (this mission) for the retirement
decision and its rationale.

**Disposition**: preserved here for historical/forensic reference only. It is
not part of the active migration chain (`migrations/002` → `003` → `004` →
`005`) and must not be run against any canonical database. The canonical
bootstrap path is: `Base.metadata.create_all()` (creates all ORM tables,
including what 001 used to create) followed by migrations 002 → 003 → 004 → 005
in order.
