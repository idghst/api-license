import tomllib
from pathlib import Path

from app.schemas import LicenseCreate, LicensePatch, LicenseRecord

PROJECT_ROOT = Path(__file__).resolve().parents[1]

LICENSE_RECORD_COLUMNS = {
    "id",
    "product_name",
    "vendor",
    "total_seats",
    "used_seats",
    "start_date",
    "expires_at",
    "renewal_date",
    "status",
    "memo",
    "created_at",
    "updated_at",
    "partnership_contact",
    "business_contact",
    "contract_contact",
    "license_configuration",
    "affiliate",
}
LICENSE_WRITABLE_COLUMNS = LICENSE_RECORD_COLUMNS - {
    "id",
    "status",
    "created_at",
    "updated_at",
}


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


def test_license_contacts_migration_extracts_legacy_memo_fields() -> None:
    migrations = sorted(
        (PROJECT_ROOT / "supabase" / "migrations").glob(
            "*_add_license_contacts_contract_and_configuration.sql"
        )
    )

    assert len(migrations) == 1
    migration = migrations[0].read_text(encoding="utf-8")

    assert "add column partnership_contact" in migration
    assert "add column business_contact" in migration
    assert "add column contract_contact" in migration
    assert "add column license_configuration" in migration
    assert r"\[제휴 담당자\]" in migration
    assert r"\[사업 담당자\]" in migration
    assert r"\[계약 담당자\]" in migration
    assert r"\[계약 만료일\]" in migration
    assert r"\[라이선스 구성\]" in migration
    assert r"\[기존 상태 코드\]" in migration


def test_license_affiliate_migration_keeps_the_field_optional_and_bounded() -> None:
    migrations = sorted(
        (PROJECT_ROOT / "supabase" / "migrations").glob("*_add_license_affiliate.sql")
    )

    assert len(migrations) == 1
    migration = migrations[0].read_text(encoding="utf-8")

    assert "add column affiliate text" in migration
    assert "affiliate is null or char_length(affiliate) <= 200" in migration


def test_license_schemas_match_migration_columns() -> None:
    assert set(LicenseRecord.model_fields) == LICENSE_RECORD_COLUMNS
    assert set(LicenseCreate.model_fields) == LICENSE_WRITABLE_COLUMNS
    assert set(LicensePatch.model_fields) == LICENSE_WRITABLE_COLUMNS


def test_license_record_ignores_unknown_store_columns() -> None:
    record = LicenseRecord.model_validate(
        {
            "id": "f8f121d4-1f2f-4bd7-85fb-71543800bf0f",
            "product_name": "Figma",
            "vendor": "Figma, Inc.",
            "total_seats": 12,
            "used_seats": 8,
            "start_date": "2026-01-01",
            "expires_at": "2099-01-01",
            "renewal_date": "2026-12-15",
            "status": "expired",
            "memo": None,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-02T00:00:00+00:00",
            "unknown_column": "ignored",
        }
    )

    assert record.status == "active"
    assert "unknown_column" not in record.model_fields
