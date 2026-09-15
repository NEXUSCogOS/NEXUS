# F6 REPRODUCIBILITY PROTOCOL
**NEXUS Federation F6 — 2026-08-28**

## Regenerating the DAT.AI trigger source from scratch

The F6 trigger's underlying evidence
(`systems/dat_ai/data/f6_evidence/planning_zones_dong_nai.db`) is not
committed to git (matches this estate's `*.db` policy) and requires
`geoalchemy2`/`shapely`, unavailable in the default sandboxed
environment used for this mission's regression runs. To regenerate:

```bash
cd systems/dat_ai
python3 -m venv /path/to/venv
/path/to/venv/bin/pip install geoalchemy2 shapely sqlalchemy pydantic
/path/to/venv/bin/python3 <<'EOF'
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models import PlanningZone
from worker.tasks.ingest_zoning_data import ingest_zoning_data

engine = create_engine("sqlite:///data/f6_evidence/planning_zones_dong_nai.db")
with engine.begin() as conn:
    conn.execute(text("""
    CREATE TABLE planning_zones (
        id INTEGER PRIMARY KEY, project_id VARCHAR(100) UNIQUE NOT NULL,
        project_name VARCHAR(500) NOT NULL, administrative_code VARCHAR(50),
        name VARCHAR(255) NOT NULL, zone_type VARCHAR(100), description TEXT,
        zone_category VARCHAR(100), sub_categories TEXT, geom TEXT,
        data_confidence FLOAT NOT NULL DEFAULT 0.95,
        validation_status VARCHAR(50) DEFAULT 'ingested', source_url TEXT,
        ingestion_date DATETIME, created_at DATETIME, updated_at DATETIME
    )
    """))
session = sessionmaker(bind=engine)()
print(ingest_zoning_data("data/zoning_raw/dong_nai_2024.json", "Dong Nai", 0.95, session=session))
EOF
```

Raw DDL (not `Base.metadata.create_all()`) is required because
`geoalchemy2`'s `Geometry` column type registers a SpatiaLite-only DDL
event hook that fails outside a real SpatiaLite/PostGIS environment; the
ORM read/write path itself (`ingest_zoning_data`, `PlanningZone`) is
DAT.AI's own, completely unmodified.

## Running the F6 suite

```bash
cd systems/nexus_federation
PYTHONPATH="../dat_ai:." python3 -m pytest tests/f6/ -v -s
```

No PostGIS/geoalchemy2 dependency for the test suite itself — the
trigger source subprocess (`process_dat_ai_trigger_source.py`) reads the
already-ingested SQLite artifact with plain `sqlite3`, not the ORM.

## Determinism guarantees

| Value | Deterministic? | Basis |
|---|---|---|
| `trigger_id` | Yes | `uuid5(NAMESPACE_URL, f"f6-trigger:{dat_ai_cycle_id}:{zone_project_id}")` |
| delegation `proposal_id` (both missions) | Yes | `uuid5(NAMESPACE_URL, f"f6-delegation:{trigger_id}:{recipient}")` |
| delegation `mission_id` (both missions) | Yes | `f"{trigger_id}-mission-l"` / `"-mission-s"` |
| `synthesis_id` | No (fresh per computation) | Deliberate — see NEXUS_EXECUTIVE_SYNTHESIS_MODEL.md |
| DAT.AI report `cycle_id` | No (fresh uuid4 per ingestion) | Each DAT.AI ingestion IS a genuinely new report; replaying the SAME already-accepted report (not re-ingesting) is what `last_accepted_report()` reads for trigger construction |

## Environment-specific regression commands

```bash
# NEXUS federation (includes F6)
cd systems/nexus_federation
PYTHONPATH="../dat_ai:." python3 -m pytest tests/ -q

# Librarian
cd systems/librarian
PYTHONPATH="../dat_ai:../nexus_federation:." python3 -m pytest tests/ -q

# Sentinel (native repo + F5.1 harness)
PYTHONPATH=~ python3 -m pytest ~/sentinel/tests/ -q
cd systems/sentinel && python3 -m pytest tests/f5/ -q

# DAT.AI (collectible subset; geoalchemy2-dependent zoning tests require
# the dedicated venv above)
cd systems/dat_ai
python3 -m pytest tests/ -q \
  --ignore=tests/integration/ingestion/test_zoning_ingestion.py \
  --ignore=tests/integration/routes/test_zoning_routes.py \
  --ignore=tests/unit/models/test_zoning.py
```
