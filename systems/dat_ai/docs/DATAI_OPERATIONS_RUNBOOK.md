# DAT.AI Operations Runbook

**Status**: GROUNDED — every command below was actually run during Phase C verification.

## Local development / testing bootstrap

```bash
# 1. Stand up a disposable PostGIS instance (never touch a production cluster)
initdb -D <scratch-pgdata> --auth=trust --username=$(whoami) --encoding=UTF8 --locale=en_US.UTF-8
pg_ctl -D <scratch-pgdata> -l <logfile> -o "-p 5545 -h 127.0.0.1" start
createdb -h 127.0.0.1 -p 5545 datai_test
psql -h 127.0.0.1 -p 5545 -d datai_test -c "CREATE EXTENSION postgis;"

# 2. Bootstrap schema (ORM first, then migrations in order)
cd systems/dat_ai
export DATABASE_URL="postgresql://$(whoami)@127.0.0.1:5545/datai_test"
python3 -c "from sqlalchemy import create_engine; from app.models import Base; Base.metadata.create_all(create_engine('$DATABASE_URL'))"
for m in migrations/002_*.sql migrations/003_*.sql migrations/004_*.sql migrations/005_*.sql; do
  psql -h 127.0.0.1 -p 5545 -d datai_test -f "$m"
done
# NEVER run migrations/retired/001_satellite_tables.sql.retired

# 3. Run tests
export DAT_AI_RUNTIME_MODE=test
export TEST_DATABASE_URL="$DATABASE_URL"
export MODEL_PATH=/path/to/satellite_classifier_v1.2.pth  # external storage, see MODEL_REGISTRY_METADATA.json
export PYTHONPATH=.
python3 -m pytest -q

# 4. Teardown (always, after testing)
pg_ctl -D <scratch-pgdata> stop -m fast
rm -rf <scratch-pgdata>
```

## Health check interpretation

`GET /readiness` returns 200 only when database, postgis, migrations, and
configuration are all healthy (production mode additionally requires
classifier healthy and satellite_ingestion healthy-or-disabled). A 503 is
the correct, intended response when prerequisites are missing — do not
treat 503 as a bug; read the `problems` array in the response body for the
exact cause.

## Known operational limitations (see `DATAI_LIMITATIONS.md` for full list)

- No satellite acquisition capability (credentials absent)
- Model checkpoint present but untrained — do not enable
  `MODEL_PROMOTED_FOR_PRODUCTION` expecting real inference; the promotion
  gate will reject it regardless (by design)
- No production deployment exists; this runbook covers local/test only
