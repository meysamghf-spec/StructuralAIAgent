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
        "010_agent_builder_foundation.sql",
        "011_analysis_engine_foundation.sql",
        "012_design_engine_foundation.sql",
        "013_optimization_engine_foundation.sql",
        "014_external_solver_integration_foundation.sql",
        "015_engineering_result_ingestion_foundation.sql",
        "016_cad_drawing_foundation.sql",
        "017_crypto_payment_foundation.sql",
        "018_user_identity_foundation.sql",
        "019_agent_execution_lifecycle.sql",
        "020_conversations_foundation.sql",
        "021_engineering_learning_foundation.sql",
        "022_seed_agent_capabilities.sql",
        "030_platform_issues.sql",
        "031_platform_issues_details.sql",
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


def test_agent_builder_migration_defines_builder_tables() -> None:
    sql = (get_migrations_dir() / "010_agent_builder_foundation.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS agent_version_tests" in sql
    assert "CREATE TABLE IF NOT EXISTS agent_builder_publications" in sql
    assert "project_id UUID" in sql
    assert "('010', 'agent_builder_foundation')" in sql


def test_analysis_engine_migration_defines_analysis_runs_table() -> None:
    sql = (get_migrations_dir() / "011_analysis_engine_foundation.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS analysis_runs" in sql
    assert "REFERENCES projects(id) ON DELETE CASCADE" in sql
    assert "('011', 'analysis_engine_foundation')" in sql


def test_design_engine_migration_defines_design_runs_table() -> None:
    sql = (get_migrations_dir() / "012_design_engine_foundation.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS design_runs" in sql
    assert "REFERENCES analysis_runs(id)" in sql
    assert "('012', 'design_engine_foundation')" in sql


def test_optimization_engine_migration_defines_optimization_runs_table() -> None:
    sql = (get_migrations_dir() / "013_optimization_engine_foundation.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS optimization_runs" in sql
    assert "REFERENCES design_runs(id)" in sql
    assert "REFERENCES analysis_runs(id)" in sql
    assert "('013', 'optimization_engine_foundation')" in sql


def test_external_solver_integration_migration_defines_integration_executions() -> None:
    sql = (get_migrations_dir() / "014_external_solver_integration_foundation.sql").read_text(
        encoding="utf-8"
    )
    assert "CREATE TABLE IF NOT EXISTS integration_executions" in sql
    assert "REQUIRES_LOCAL_SOFTWARE" in sql
    assert "('014', 'external_solver_integration_foundation')" in sql


def test_engineering_result_ingestion_migration_defines_result_sets() -> None:
    sql = (get_migrations_dir() / "015_engineering_result_ingestion_foundation.sql").read_text(
        encoding="utf-8"
    )
    assert "CREATE TABLE IF NOT EXISTS engineering_result_sets" in sql
    assert "engineering_results_available" in sql
    assert "('015', 'engineering_result_ingestion_foundation')" in sql


def test_cad_drawing_migration_defines_cad_drawings() -> None:
    sql = (get_migrations_dir() / "016_cad_drawing_foundation.sql").read_text(
        encoding="utf-8"
    )
    assert "CREATE TABLE IF NOT EXISTS cad_drawings" in sql
    assert "validation_status" in sql
    assert "('016', 'cad_drawing_foundation')" in sql


def test_crypto_payment_migration_defines_payment_tables() -> None:
    sql = (get_migrations_dir() / "017_crypto_payment_foundation.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS crypto_payments" in sql
    assert "CREATE TABLE IF NOT EXISTS upgrade_entitlements" in sql
    assert "CREATE TABLE IF NOT EXISTS payment_audit_events" in sql
    assert "('017', 'crypto_payment_foundation')" in sql


def test_engineering_learning_migration_defines_records_and_uses() -> None:
    sql = (get_migrations_dir() / "021_engineering_learning_foundation.sql").read_text(
        encoding="utf-8"
    )
    assert "CREATE TABLE IF NOT EXISTS engineering_learning_records" in sql
    assert "CREATE TABLE IF NOT EXISTS engineering_learning_uses" in sql
    assert "PROJECT" in sql and "ENGINEER" in sql and "GLOBAL" in sql
    assert "CANDIDATE" in sql and "APPROVED" in sql and "REJECTED" in sql
    assert "('021', 'engineering_learning_foundation')" in sql


def test_user_identity_migration_defines_users_and_project_ownership() -> None:
    sql = (get_migrations_dir() / "018_user_identity_foundation.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS users" in sql
    assert "owner_account_id" in sql
    assert "('018', 'user_identity_foundation')" in sql

