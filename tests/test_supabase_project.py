import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_local_supabase_project_exposes_only_license_schema_contract() -> None:
    config = tomllib.loads(
        (PROJECT_ROOT / "supabase" / "config.toml").read_text(encoding="utf-8")
    )

    assert config["project_id"] == "fastapi-license"
    assert config["api"]["schemas"] == ["public", "graphql_public", "license"]


def test_license_migration_limits_default_privileges_to_service_role() -> None:
    migrations = sorted(
        (PROJECT_ROOT / "supabase" / "migrations").glob("*_init_license.sql")
    )

    assert len(migrations) == 1
    migration = migrations[0].read_text(encoding="utf-8")

    assert "create schema if not exists license;" in migration
    assert (
        "grant usage on schema license to anon, authenticated, service_role;"
        in migration
    )
    assert "grant all on tables to service_role;" in migration
    assert "grant all on sequences to service_role;" in migration
    assert "grant execute on routines to service_role;" in migration
    assert "grant all on tables to anon" not in migration
    assert "grant all on tables to authenticated" not in migration


def test_license_records_migration_keeps_records_private_to_the_server() -> None:
    migrations = sorted(
        (PROJECT_ROOT / "supabase" / "migrations").glob("*_create_license_records.sql")
    )

    assert len(migrations) == 1
    migration = migrations[0].read_text(encoding="utf-8")

    assert "create table license.license_records" in migration
    assert "alter table license.license_records enable row level security;" in migration
    assert "revoke usage on schema license from anon, authenticated;" in migration
    assert (
        "revoke all privileges on table license.license_records from anon, authenticated;"
        in migration
    )
    assert (
        "grant select, insert, update, delete on table license.license_records to service_role;"
        in migration
    )
    assert "total_seats >= 1" in migration
    assert "used_seats <= total_seats" in migration
