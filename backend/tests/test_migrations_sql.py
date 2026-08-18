"""Static checks for SQL migrations (no database required)."""

from pathlib import Path

from app.infrastructure.database.migrations import get_migrations_dir


def test_migrations_directory_contains_bootstrap_and_pem_foundation() -> None:
    migrations_dir = get_migrations_dir()
    files = sorted(path.name for path in migrations_dir.glob("*.sql"))
    assert files == [
        "001_bootstrap.sql",
        "002_pem_foundation.sql",
        "003_agent_foundation.sql",
        "004_file_ingestion_foundation.sql",
        "005_project_memory_foundation.sql",
        "006_human_approval_foundation.sql",
        "007_traceability_foundation.sql",
        "008_engineering_reporting_foundation.sql",
        "009_agent_runtime_foundation.sql",
    ]


def test_engineering_reporting_migration_defines_core_tables() -> None:
    sql = (get_migrations_dir() / "008_engineering_reporting_foundation.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS reports" in sql
    assert "CREATE TABLE IF NOT EXISTS report_versions" in sql
    assert "REFERENCES projects(id) ON DELETE CASCADE" in sql
    assert "('008', 'engineering_reporting_foundation')" in sql


def test_traceability_migration_defines_core_table() -> None:
    sql = (get_migrations_dir() / "007_traceability_foundation.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS traceability_links" in sql
    assert "REFERENCES projects(id) ON DELETE CASCADE" in sql
    assert "('007', 'traceability_foundation')" in sql


def test_human_approval_migration_defines_core_tables() -> None:
    sql = (get_migrations_dir() / "006_human_approval_foundation.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS human_approval_requests" in sql
    assert "CREATE TABLE IF NOT EXISTS human_approval_events" in sql
    assert "REFERENCES projects(id) ON DELETE CASCADE" in sql
    assert "('006', 'human_approval_foundation')" in sql


def test_project_memory_migration_defines_core_table() -> None:
    sql = (get_migrations_dir() / "005_project_memory_foundation.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS project_memory" in sql
    assert "REFERENCES projects(id) ON DELETE CASCADE" in sql
    assert "('005', 'project_memory_foundation')" in sql


def test_file_ingestion_migration_defines_project_files_table() -> None:
    sql = (get_migrations_dir() / "004_file_ingestion_foundation.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS project_files" in sql
    assert "REFERENCES projects(id) ON DELETE CASCADE" in sql
    assert "('004', 'file_ingestion_foundation')" in sql
    assert "CREATE TABLE IF NOT EXISTS agent_executions" not in sql


def test_agent_foundation_migration_defines_core_tables() -> None:
    sql = (get_migrations_dir() / "003_agent_foundation.sql").read_text(encoding="utf-8")
    for table in (
        "agent_definitions",
        "agent_versions",
        "agent_capabilities",
        "agent_version_capabilities",
        "prompt_templates",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
    assert "('003', 'agent_foundation')" in sql
    assert "CREATE TABLE IF NOT EXISTS agent_executions" not in sql


def test_pem_foundation_migration_defines_core_tables() -> None:
    sql = (get_migrations_dir() / "002_pem_foundation.sql").read_text(encoding="utf-8")
    for table in ("projects", "pem_snapshots", "revisions"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
    assert "snapshot_data JSONB NOT NULL" in sql
    assert "('002', 'pem_foundation')" in sql


def test_bootstrap_migration_is_unchanged_minimum() -> None:
    sql = (get_migrations_dir() / "001_bootstrap.sql").read_text(encoding="utf-8")
    assert "schema_migrations" in sql
    assert "CREATE TABLE IF NOT EXISTS projects" not in sql


def test_agent_runtime_migration_defines_core_tables() -> None:
    sql = (get_migrations_dir() / "009_agent_runtime_foundation.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS agent_executions" in sql
    assert "ALTER TABLE agent_definitions" in sql
    assert "agent_type VARCHAR(64)" in sql
    assert "REFERENCES projects(id) ON DELETE CASCADE" in sql
    assert "('009', 'agent_runtime_foundation')" in sql
