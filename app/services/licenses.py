from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from fastapi import Response
from fastapi import status as http_status
from postgrest.exceptions import APIError
from pydantic import ValidationError

from app.core.errors import ApiError
from app.schemas import LicenseCreate, LicenseList, LicensePatch, LicenseRecord
from supabase import AsyncClient

TABLE_NAME = "license_records"


async def _execute(operation: Callable[[], Any]) -> Any:
    try:
        return await operation()
    except (APIError, httpx.HTTPError) as error:
        raise ApiError(
            503, "license_store_unavailable", "License storage is unavailable"
        ) from error


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


async def list_licenses(client: AsyncClient) -> LicenseList:
    response = await _execute(
        lambda: (
            client.table(TABLE_NAME)
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
    )
    records = [LicenseRecord.model_validate(item) for item in response.data]
    return LicenseList(items=records, count=len(records))


async def create_license(
    client: AsyncClient, license_input: LicenseCreate
) -> LicenseRecord:
    response = await _execute(
        lambda: (
            client.table(TABLE_NAME)
            .insert(license_input.model_dump(mode="json", exclude_none=True))
            .execute()
        )
    )
    if not response.data:
        raise ApiError(
            503, "license_store_unavailable", "License storage is unavailable"
        )
    return LicenseRecord.model_validate(response.data[0])


async def get_license(client: AsyncClient, license_id: UUID) -> LicenseRecord:
    response = await _execute(
        lambda: (
            client.table(TABLE_NAME)
            .select("*")
            .eq("id", str(license_id))
            .limit(1)
            .execute()
        )
    )
    if not response.data:
        raise ApiError(404, "license_not_found", "License was not found")
    return LicenseRecord.model_validate(response.data[0])


async def update_license(
    client: AsyncClient,
    license_id: UUID,
    license_input: LicensePatch,
) -> LicenseRecord:
    existing_response = await _execute(
        lambda: (
            client.table(TABLE_NAME)
            .select("*")
            .eq("id", str(license_id))
            .limit(1)
            .execute()
        )
    )
    if not existing_response.data:
        raise ApiError(404, "license_not_found", "License was not found")
    existing = LicenseRecord.model_validate(existing_response.data[0])
    changes = license_input.model_dump(exclude_unset=True, mode="json")
    _validate_patch(existing, changes)
    changes["updated_at"] = datetime.now(UTC).isoformat()

    updated_response = await _execute(
        lambda: (
            client.table(TABLE_NAME).update(changes).eq("id", str(license_id)).execute()
        )
    )
    if not updated_response.data:
        raise ApiError(404, "license_not_found", "License was not found")
    return LicenseRecord.model_validate(updated_response.data[0])


async def delete_license(client: AsyncClient, license_id: UUID) -> Response:
    response = await _execute(
        lambda: client.table(TABLE_NAME).delete().eq("id", str(license_id)).execute()
    )
    if not response.data:
        raise ApiError(404, "license_not_found", "License was not found")
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
