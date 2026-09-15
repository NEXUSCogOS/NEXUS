from pathlib import Path

def _script():
    repo = Path(__file__).resolve().parents[4]
    path = repo / "ops" / "backup" / "sentinel_db_backup.sh"
    assert path.exists()
    return path.read_text()

def test_uses_verified_sources():
    s = _script()
    assert "$HOME/.local/logs/scalpers/scalper_data.db" in s
    assert "$HOME/.local/logs/scalpers/labs.db" in s
    assert "$HOME/NEXUS/systems/engineering_studio/runtime/sentinel_financial.db" in s

def test_rejects_stale_sources():
    s = _script()
    assert "$HOME/sentinel/sentinel.db" not in s
    assert "$HOME/sentinel/financial_intelligence.db" not in s

def test_uses_sqlite_backup_and_integrity_checks():
    s = _script()
    assert ".backup" in s
    assert "PRAGMA quick_check" in s
    assert "BACKUP_INTEGRITY_FAILED" in s
    assert "SOURCE_INTEGRITY_FAILED" in s

def test_records_provenance():
    s = _script()
    assert "sha256" in s
    assert "backup_manifest_" in s
    assert "source_bytes" in s
    assert "backup_bytes" in s

def test_cleans_temporary_sqlite_sidecars():
    s = _script()
    assert 'rm -f "${TMP}-wal" "${TMP}-shm"' in s

def test_retention_is_scoped():
    s = _script()
    assert 'find "$BACKUP_DIR"' in s
    assert "-maxdepth 1" in s
    assert "scalper_data_*.db" in s
    assert "labs_*.db" in s
    assert "sentinel_financial_*.db" in s
