import hmac
from datetime import UTC, date, datetime
from typing import Annotated, Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header, Response
from fastapi import status as http_status
from postgrest.exceptions import APIError
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.integrations.supabase import get_admin_client
from supabase import AsyncClient

router = APIRouter(prefix="/licenses", tags=["licenses"])


def _camel_case(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


class LicenseRecord(BaseModel):
    model_config = ConfigDict(alias_generator=_camel_case, populate_by_name=True)

    id: UUID
    product_name: str
    vendor: str
    total_seats: int
    used_seats: int
    start_date: date | None
    expires_at: date | None
    renewal_date: date | None
    status: str
    memo: str | None
    created_at: datetime
    updated_at: datetime


class LicenseList(BaseModel):
    items: list[LicenseRecord]
    count: int


LicenseStatus = Literal["active", "expiring", "expired", "inactive"]


class LicenseCreate(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel_case,
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    product_name: Annotated[str, Field(min_length=1, max_length=200)]
    vendor: Annotated[str, Field(min_length=1, max_length=200)]
    total_seats: Annotated[int, Field(ge=1, le=1_000_000)]
    used_seats: Annotated[int, Field(ge=0, le=1_000_000)]
    start_date: date | None = None
    expires_at: date | None = None
    renewal_date: date | None = None
    status: LicenseStatus = "active"
    memo: Annotated[str | None, Field(max_length=5_000)] = None

    @model_validator(mode="after")
    def require_consistent_license_details(self) -> "LicenseCreate":
        if self.used_seats > self.total_seats:
            raise ValueError("usedSeats must not exceed totalSeats")
        if self.start_date and self.expires_at and self.expires_at < self.start_date:
            raise ValueError("expiresAt must not be before startDate")
        return self


class LicensePatch(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel_case,
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    product_name: Annotated[str | None, Field(min_length=1, max_length=200)] = None
    vendor: Annotated[str | None, Field(min_length=1, max_length=200)] = None
    total_seats: Annotated[int | None, Field(ge=1, le=1_000_000)] = None
    used_seats: Annotated[int | None, Field(ge=0, le=1_000_000)] = None
    start_date: date | None = None
    expires_at: date | None = None
    renewal_date: date | None = None
    status: LicenseStatus | None = None
    memo: Annotated[str | None, Field(max_length=5_000)] = None

    @model_validator(mode="after")
    def require_at_least_one_change(self) -> "LicensePatch":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        return self


def require_admin_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    x_admin_key: Annotated[str | None, Header()] = None,
) -> None:
    if settings.ADMIN_API_KEY is None:
        raise ApiError(
            503,
            "administrator_authentication_unavailable",
            "Administrator authentication is unavailable",
        )

    if x_admin_key is None or not hmac.compare_digest(
        x_admin_key, settings.ADMIN_API_KEY.get_secret_value()
    ):
        raise ApiError(
            401,
            "administrator_authentication_required",
            "Valid X-Admin-Key is required",
        )


@router.get("")
async def list_licenses(
    _: Annotated[None, Depends(require_admin_api_key)],
    client: Annotated[AsyncClient, Depends(get_admin_client)],
) -> LicenseList:
    try:
        response = await (
            client.table("licenses")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
    except (APIError, httpx.HTTPError) as error:
        raise ApiError(
            503, "license_store_unavailable", "License storage is unavailable"
        ) from error

    records = [LicenseRecord.model_validate(item) for item in response.data]
    return LicenseList(items=records, count=len(records))


@router.post("", response_model=LicenseRecord, status_code=http_status.HTTP_201_CREATED)
async def create_license(
    license_input: LicenseCreate,
    _: Annotated[None, Depends(require_admin_api_key)],
    client: Annotated[AsyncClient, Depends(get_admin_client)],
) -> LicenseRecord:
    try:
        response = await (
            client.table("licenses")
            .insert(license_input.model_dump(mode="json"))
            .execute()
        )
    except (APIError, httpx.HTTPError) as error:
        raise ApiError(
            503, "license_store_unavailable", "License storage is unavailable"
        ) from error

    if not response.data:
        raise ApiError(
            503, "license_store_unavailable", "License storage is unavailable"
        )
    return LicenseRecord.model_validate(response.data[0])


@router.get("/{license_id}", response_model=LicenseRecord)
async def get_license(
    license_id: UUID,
    _: Annotated[None, Depends(require_admin_api_key)],
    client: Annotated[AsyncClient, Depends(get_admin_client)],
) -> LicenseRecord:
    try:
        response = await (
            client.table("licenses")
            .select("*")
            .eq("id", str(license_id))
            .limit(1)
            .execute()
        )
    except (APIError, httpx.HTTPError) as error:
        raise ApiError(
            503, "license_store_unavailable", "License storage is unavailable"
        ) from error

    if not response.data:
        raise ApiError(404, "license_not_found", "License was not found")
    return LicenseRecord.model_validate(response.data[0])


def _validate_patch(existing: LicenseRecord, changes: dict[str, object]) -> None:
    merged = {
        field_name: getattr(existing, field_name)
        for field_name in LicenseCreate.model_fields
    }
    merged.update(changes)
    try:
        LicenseCreate.model_validate(merged)
    except ValidationError as error:
        raise ApiError(422, "validation_error", "Request validation failed") from error


@router.patch("/{license_id}", response_model=LicenseRecord)
async def update_license(
    license_id: UUID,
    license_input: LicensePatch,
    _: Annotated[None, Depends(require_admin_api_key)],
    client: Annotated[AsyncClient, Depends(get_admin_client)],
) -> LicenseRecord:
    try:
        existing_response = await (
            client.table("licenses")
            .select("*")
            .eq("id", str(license_id))
            .limit(1)
            .execute()
        )
    except (APIError, httpx.HTTPError) as error:
        raise ApiError(
            503, "license_store_unavailable", "License storage is unavailable"
        ) from error

    if not existing_response.data:
        raise ApiError(404, "license_not_found", "License was not found")
    existing = LicenseRecord.model_validate(existing_response.data[0])
    changes = license_input.model_dump(exclude_unset=True, mode="json")
    _validate_patch(existing, changes)
    changes["updated_at"] = datetime.now(UTC).isoformat()

    try:
        updated_response = await (
            client.table("licenses").update(changes).eq("id", str(license_id)).execute()
        )
    except (APIError, httpx.HTTPError) as error:
        raise ApiError(
            503, "license_store_unavailable", "License storage is unavailable"
        ) from error

    if not updated_response.data:
        raise ApiError(404, "license_not_found", "License was not found")
    return LicenseRecord.model_validate(updated_response.data[0])


@router.delete("/{license_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_license(
    license_id: UUID,
    _: Annotated[None, Depends(require_admin_api_key)],
    client: Annotated[AsyncClient, Depends(get_admin_client)],
) -> Response:
    try:
        response = await (
            client.table("licenses").delete().eq("id", str(license_id)).execute()
        )
    except (APIError, httpx.HTTPError) as error:
        raise ApiError(
            503, "license_store_unavailable", "License storage is unavailable"
        ) from error

    if not response.data:
        raise ApiError(404, "license_not_found", "License was not found")
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
