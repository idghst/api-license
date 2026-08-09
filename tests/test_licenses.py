from typing import Any

import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


class FakeResponse:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class FakeSelectQuery:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    def select(self, *_: str) -> "FakeSelectQuery":
        return self

    def order(self, _: str, *, desc: bool = False) -> "FakeSelectQuery":
        assert desc is True
        return self

    def eq(self, column: str, value: str) -> "FakeSelectQuery":
        assert column == "id"
        assert value == "f8f121d4-1f2f-4bd7-85fb-71543800bf0f"
        return self

    def limit(self, count: int) -> "FakeSelectQuery":
        assert count == 1
        return self

    async def execute(self) -> FakeResponse:
        return self.response


class FakeAdminClient:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.response = FakeResponse(data)

    def table(self, name: str) -> FakeSelectQuery:
        assert name == "licenses"
        return FakeSelectQuery(self.response)


class FakeInsertQuery:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.inserted: dict[str, Any] | None = None

    def insert(self, payload: dict[str, Any]) -> "FakeInsertQuery":
        self.inserted = payload
        return self

    async def execute(self) -> FakeResponse:
        return self.response


class FakeInsertClient:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.query = FakeInsertQuery(FakeResponse(data))

    def table(self, name: str) -> FakeInsertQuery:
        assert name == "licenses"
        return self.query


class FakePatchQuery:
    def __init__(
        self, existing: list[dict[str, Any]], updated: list[dict[str, Any]]
    ) -> None:
        self.existing = FakeResponse(existing)
        self.updated_response = FakeResponse(updated)
        self.updated: dict[str, Any] | None = None

    def select(self, *_: str) -> "FakePatchQuery":
        return self

    def eq(self, column: str, value: str) -> "FakePatchQuery":
        assert column == "id"
        assert value == "f8f121d4-1f2f-4bd7-85fb-71543800bf0f"
        return self

    def limit(self, count: int) -> "FakePatchQuery":
        assert count == 1
        return self

    def update(self, payload: dict[str, Any]) -> "FakePatchQuery":
        self.updated = payload
        return self

    async def execute(self) -> FakeResponse:
        return self.updated_response if self.updated is not None else self.existing


class FakePatchClient:
    def __init__(
        self, existing: list[dict[str, Any]], updated: list[dict[str, Any]]
    ) -> None:
        self.query = FakePatchQuery(existing, updated)

    def table(self, name: str) -> FakePatchQuery:
        assert name == "licenses"
        return self.query


class FakeDeleteQuery:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.deleted = False

    def delete(self) -> "FakeDeleteQuery":
        self.deleted = True
        return self

    def eq(self, column: str, value: str) -> "FakeDeleteQuery":
        assert column == "id"
        assert value == "f8f121d4-1f2f-4bd7-85fb-71543800bf0f"
        return self

    async def execute(self) -> FakeResponse:
        return self.response


class FakeDeleteClient:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.query = FakeDeleteQuery(FakeResponse(data))

    def table(self, name: str) -> FakeDeleteQuery:
        assert name == "licenses"
        return self.query


class FailingAdminClient:
    def table(self, _: str) -> None:
        raise httpx.ConnectError("private upstream details")


def valid_license_payload() -> dict[str, object]:
    return {
        "productName": "Figma",
        "vendor": "Figma, Inc.",
        "totalSeats": 12,
        "usedSeats": 8,
        "startDate": "2026-01-01",
        "expiresAt": "2027-01-01",
        "renewalDate": "2026-12-15",
        "status": "active",
        "memo": "Design team",
    }


def test_list_licenses_requires_an_admin_key() -> None:
    app = create_app(
        Settings(
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
            SUPABASE_SECRET_KEY="sb_secret_test",
            ADMIN_API_KEY="admin-test-key",
        )
    )

    response = TestClient(app).get("/api/v1/licenses")

    assert response.status_code == 401
    assert response.json()["code"] == "administrator_authentication_required"


def test_list_licenses_returns_admin_records_in_camel_case() -> None:
    from app.integrations.supabase import get_admin_client

    app = create_app(
        Settings(
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
            SUPABASE_SECRET_KEY="sb_secret_test",
            ADMIN_API_KEY="admin-test-key",
        )
    )
    admin_client = FakeAdminClient(
        [
            {
                "id": "f8f121d4-1f2f-4bd7-85fb-71543800bf0f",
                "product_name": "Figma",
                "vendor": "Figma, Inc.",
                "total_seats": 12,
                "used_seats": 8,
                "start_date": "2026-01-01",
                "expires_at": "2027-01-01",
                "renewal_date": "2026-12-15",
                "status": "active",
                "memo": "Design team",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-02T00:00:00+00:00",
            }
        ]
    )

    async def provide_admin_client():
        yield admin_client

    app.dependency_overrides[get_admin_client] = provide_admin_client
    response = TestClient(app).get(
        "/api/v1/licenses", headers={"X-Admin-Key": "admin-test-key"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": "f8f121d4-1f2f-4bd7-85fb-71543800bf0f",
                "productName": "Figma",
                "vendor": "Figma, Inc.",
                "totalSeats": 12,
                "usedSeats": 8,
                "startDate": "2026-01-01",
                "expiresAt": "2027-01-01",
                "renewalDate": "2026-12-15",
                "status": "active",
                "memo": "Design team",
                "createdAt": "2026-01-01T00:00:00Z",
                "updatedAt": "2026-01-02T00:00:00Z",
            }
        ],
        "count": 1,
    }


def test_get_license_returns_one_admin_record_in_camel_case() -> None:
    from app.integrations.supabase import get_admin_client

    app = create_app(
        Settings(
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
            SUPABASE_SECRET_KEY="sb_secret_test",
            ADMIN_API_KEY="admin-test-key",
        )
    )
    admin_client = FakeAdminClient(
        [
            {
                "id": "f8f121d4-1f2f-4bd7-85fb-71543800bf0f",
                "product_name": "Figma",
                "vendor": "Figma, Inc.",
                "total_seats": 12,
                "used_seats": 8,
                "start_date": "2026-01-01",
                "expires_at": "2027-01-01",
                "renewal_date": "2026-12-15",
                "status": "active",
                "memo": "Design team",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-02T00:00:00+00:00",
            }
        ]
    )

    async def provide_admin_client():
        yield admin_client

    app.dependency_overrides[get_admin_client] = provide_admin_client
    response = TestClient(app).get(
        "/api/v1/licenses/f8f121d4-1f2f-4bd7-85fb-71543800bf0f",
        headers={"X-Admin-Key": "admin-test-key"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == "f8f121d4-1f2f-4bd7-85fb-71543800bf0f"
    assert response.json()["productName"] == "Figma"


def test_create_license_persists_a_validated_record() -> None:
    from app.integrations.supabase import get_admin_client

    app = create_app(
        Settings(
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
            SUPABASE_SECRET_KEY="sb_secret_test",
            ADMIN_API_KEY="admin-test-key",
        )
    )
    admin_client = FakeInsertClient(
        [
            {
                "id": "f8f121d4-1f2f-4bd7-85fb-71543800bf0f",
                "product_name": "Figma",
                "vendor": "Figma, Inc.",
                "total_seats": 12,
                "used_seats": 8,
                "start_date": "2026-01-01",
                "expires_at": "2027-01-01",
                "renewal_date": "2026-12-15",
                "status": "active",
                "memo": "Design team",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        ]
    )

    async def provide_admin_client():
        yield admin_client

    app.dependency_overrides[get_admin_client] = provide_admin_client
    response = TestClient(app).post(
        "/api/v1/licenses",
        headers={"X-Admin-Key": "admin-test-key"},
        json={
            "productName": "Figma",
            "vendor": "Figma, Inc.",
            "totalSeats": 12,
            "usedSeats": 8,
            "startDate": "2026-01-01",
            "expiresAt": "2027-01-01",
            "renewalDate": "2026-12-15",
            "status": "active",
            "memo": "Design team",
        },
    )

    assert response.status_code == 201
    assert response.json()["productName"] == "Figma"
    assert response.json()["createdAt"] == "2026-01-01T00:00:00Z"
    assert admin_client.query.inserted == {
        "product_name": "Figma",
        "vendor": "Figma, Inc.",
        "total_seats": 12,
        "used_seats": 8,
        "start_date": "2026-01-01",
        "expires_at": "2027-01-01",
        "renewal_date": "2026-12-15",
        "status": "active",
        "memo": "Design team",
    }


def test_create_license_rejects_raw_license_keys() -> None:
    from app.integrations.supabase import get_admin_client

    app = create_app(
        Settings(
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
            SUPABASE_SECRET_KEY="sb_secret_test",
            ADMIN_API_KEY="admin-test-key",
        )
    )
    admin_client = FakeInsertClient([])

    async def provide_admin_client():
        yield admin_client

    app.dependency_overrides[get_admin_client] = provide_admin_client
    payload = valid_license_payload()
    payload["licenseKey"] = "raw-license-key"
    response = TestClient(app).post(
        "/api/v1/licenses",
        headers={"X-Admin-Key": "admin-test-key"},
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert admin_client.query.inserted is None


def test_create_license_rejects_used_seats_above_the_total() -> None:
    from app.integrations.supabase import get_admin_client

    app = create_app(
        Settings(
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
            SUPABASE_SECRET_KEY="sb_secret_test",
            ADMIN_API_KEY="admin-test-key",
        )
    )
    admin_client = FakeInsertClient([])

    async def provide_admin_client():
        yield admin_client

    app.dependency_overrides[get_admin_client] = provide_admin_client
    payload = valid_license_payload()
    payload["totalSeats"] = 2
    response = TestClient(app).post(
        "/api/v1/licenses",
        headers={"X-Admin-Key": "admin-test-key"},
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert admin_client.query.inserted is None


def test_create_license_rejects_expiration_before_the_start_date() -> None:
    from app.integrations.supabase import get_admin_client

    app = create_app(
        Settings(
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
            SUPABASE_SECRET_KEY="sb_secret_test",
            ADMIN_API_KEY="admin-test-key",
        )
    )
    admin_client = FakeInsertClient([])

    async def provide_admin_client():
        yield admin_client

    app.dependency_overrides[get_admin_client] = provide_admin_client
    payload = valid_license_payload()
    payload["expiresAt"] = "2025-12-31"
    response = TestClient(app).post(
        "/api/v1/licenses",
        headers={"X-Admin-Key": "admin-test-key"},
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert admin_client.query.inserted is None


def test_create_license_rejects_unknown_status() -> None:
    from app.integrations.supabase import get_admin_client

    app = create_app(
        Settings(
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
            SUPABASE_SECRET_KEY="sb_secret_test",
            ADMIN_API_KEY="admin-test-key",
        )
    )
    admin_client = FakeInsertClient([])

    async def provide_admin_client():
        yield admin_client

    app.dependency_overrides[get_admin_client] = provide_admin_client
    payload = valid_license_payload()
    payload["status"] = "unknown"
    response = TestClient(app).post(
        "/api/v1/licenses",
        headers={"X-Admin-Key": "admin-test-key"},
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert admin_client.query.inserted is None


def test_patch_license_validates_against_the_existing_record() -> None:
    from app.integrations.supabase import get_admin_client

    app = create_app(
        Settings(
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
            SUPABASE_SECRET_KEY="sb_secret_test",
            ADMIN_API_KEY="admin-test-key",
        )
    )
    existing = {
        "id": "f8f121d4-1f2f-4bd7-85fb-71543800bf0f",
        "product_name": "Figma",
        "vendor": "Figma, Inc.",
        "total_seats": 12,
        "used_seats": 8,
        "start_date": "2026-01-01",
        "expires_at": "2027-01-01",
        "renewal_date": "2026-12-15",
        "status": "active",
        "memo": "Design team",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    updated = {**existing, "used_seats": 9, "updated_at": "2026-02-01T00:00:00+00:00"}
    admin_client = FakePatchClient([existing], [updated])

    async def provide_admin_client():
        yield admin_client

    app.dependency_overrides[get_admin_client] = provide_admin_client
    response = TestClient(app).patch(
        "/api/v1/licenses/f8f121d4-1f2f-4bd7-85fb-71543800bf0f",
        headers={"X-Admin-Key": "admin-test-key"},
        json={"usedSeats": 9},
    )

    assert response.status_code == 200
    assert response.json()["usedSeats"] == 9
    assert admin_client.query.updated is not None
    assert admin_client.query.updated["used_seats"] == 9
    assert isinstance(admin_client.query.updated["updated_at"], str)


def test_delete_license_returns_no_content_after_a_successful_delete() -> None:
    from app.integrations.supabase import get_admin_client

    app = create_app(
        Settings(
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
            SUPABASE_SECRET_KEY="sb_secret_test",
            ADMIN_API_KEY="admin-test-key",
        )
    )
    admin_client = FakeDeleteClient([{"id": "f8f121d4-1f2f-4bd7-85fb-71543800bf0f"}])

    async def provide_admin_client():
        yield admin_client

    app.dependency_overrides[get_admin_client] = provide_admin_client
    response = TestClient(app).delete(
        "/api/v1/licenses/f8f121d4-1f2f-4bd7-85fb-71543800bf0f",
        headers={"X-Admin-Key": "admin-test-key"},
    )

    assert response.status_code == 204
    assert response.content == b""
    assert admin_client.query.deleted is True


def test_list_licenses_rejects_an_invalid_admin_key() -> None:
    app = create_app(
        Settings(
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
            SUPABASE_SECRET_KEY="sb_secret_test",
            ADMIN_API_KEY="admin-test-key",
        )
    )

    response = TestClient(app).get(
        "/api/v1/licenses",
        headers={"X-Admin-Key": "incorrect-key", "X-Request-ID": "req-admin"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "code": "administrator_authentication_required",
        "message": "Valid X-Admin-Key is required",
        "request_id": "req-admin",
    }


def test_list_licenses_reports_missing_admin_configuration() -> None:
    app = create_app(
        Settings(
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
            SUPABASE_SECRET_KEY="sb_secret_test",
        )
    )

    response = TestClient(app).get(
        "/api/v1/licenses", headers={"X-Request-ID": "req-admin-config"}
    )

    assert response.status_code == 503
    assert response.json() == {
        "code": "administrator_authentication_unavailable",
        "message": "Administrator authentication is unavailable",
        "request_id": "req-admin-config",
    }


def test_list_licenses_sanitizes_store_failures() -> None:
    from app.integrations.supabase import get_admin_client

    app = create_app(
        Settings(
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
            SUPABASE_SECRET_KEY="sb_secret_test",
            ADMIN_API_KEY="admin-test-key",
        )
    )

    async def provide_admin_client():
        yield FailingAdminClient()

    app.dependency_overrides[get_admin_client] = provide_admin_client
    response = TestClient(app).get(
        "/api/v1/licenses",
        headers={"X-Admin-Key": "admin-test-key", "X-Request-ID": "req-store"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "code": "license_store_unavailable",
        "message": "License storage is unavailable",
        "request_id": "req-store",
    }


def test_patch_license_returns_404_when_the_record_is_missing() -> None:
    from app.integrations.supabase import get_admin_client

    app = create_app(
        Settings(
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
            SUPABASE_SECRET_KEY="sb_secret_test",
            ADMIN_API_KEY="admin-test-key",
        )
    )
    admin_client = FakePatchClient([], [])

    async def provide_admin_client():
        yield admin_client

    app.dependency_overrides[get_admin_client] = provide_admin_client
    response = TestClient(app).patch(
        "/api/v1/licenses/f8f121d4-1f2f-4bd7-85fb-71543800bf0f",
        headers={"X-Admin-Key": "admin-test-key", "X-Request-ID": "req-patch-404"},
        json={"usedSeats": 9},
    )

    assert response.status_code == 404
    assert response.json() == {
        "code": "license_not_found",
        "message": "License was not found",
        "request_id": "req-patch-404",
    }


def test_patch_license_rejects_a_change_that_breaks_existing_seats() -> None:
    from app.integrations.supabase import get_admin_client

    app = create_app(
        Settings(
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
            SUPABASE_SECRET_KEY="sb_secret_test",
            ADMIN_API_KEY="admin-test-key",
        )
    )
    existing = {
        "id": "f8f121d4-1f2f-4bd7-85fb-71543800bf0f",
        "product_name": "Figma",
        "vendor": "Figma, Inc.",
        "total_seats": 12,
        "used_seats": 8,
        "start_date": "2026-01-01",
        "expires_at": "2027-01-01",
        "renewal_date": "2026-12-15",
        "status": "active",
        "memo": "Design team",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    admin_client = FakePatchClient([existing], [])

    async def provide_admin_client():
        yield admin_client

    app.dependency_overrides[get_admin_client] = provide_admin_client
    response = TestClient(app).patch(
        "/api/v1/licenses/f8f121d4-1f2f-4bd7-85fb-71543800bf0f",
        headers={"X-Admin-Key": "admin-test-key"},
        json={"totalSeats": 7},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert admin_client.query.updated is None


def test_patch_license_rejects_an_empty_change_set() -> None:
    from app.integrations.supabase import get_admin_client

    app = create_app(
        Settings(
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
            SUPABASE_SECRET_KEY="sb_secret_test",
            ADMIN_API_KEY="admin-test-key",
        )
    )
    admin_client = FakePatchClient([], [])

    async def provide_admin_client():
        yield admin_client

    app.dependency_overrides[get_admin_client] = provide_admin_client
    response = TestClient(app).patch(
        "/api/v1/licenses/f8f121d4-1f2f-4bd7-85fb-71543800bf0f",
        headers={"X-Admin-Key": "admin-test-key"},
        json={},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert admin_client.query.updated is None


def test_delete_license_returns_404_when_no_record_is_deleted() -> None:
    from app.integrations.supabase import get_admin_client

    app = create_app(
        Settings(
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
            SUPABASE_SECRET_KEY="sb_secret_test",
            ADMIN_API_KEY="admin-test-key",
        )
    )
    admin_client = FakeDeleteClient([])

    async def provide_admin_client():
        yield admin_client

    app.dependency_overrides[get_admin_client] = provide_admin_client
    response = TestClient(app).delete(
        "/api/v1/licenses/f8f121d4-1f2f-4bd7-85fb-71543800bf0f",
        headers={"X-Admin-Key": "admin-test-key", "X-Request-ID": "req-delete-404"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "code": "license_not_found",
        "message": "License was not found",
        "request_id": "req-delete-404",
    }
