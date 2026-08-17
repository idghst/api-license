from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from fastapi import status as http_status

from app.integrations.supabase import get_admin_client, require_admin_api_key
from app.schemas import (
    LicenseCreate,
    LicenseList,
    LicensePatch,
    LicenseRecord,
    calculate_license_status,
)
from app.services import licenses
from supabase import AsyncClient

router = APIRouter(prefix="/licenses", tags=["licenses"])
AdminAuth = Annotated[None, Depends(require_admin_api_key)]
AdminClient = Annotated[AsyncClient, Depends(get_admin_client)]

__all__ = [
    "calculate_license_status",
    "require_admin_api_key",
    "router",
]


@router.get("")
async def list_licenses(_: AdminAuth, client: AdminClient) -> LicenseList:
    return await licenses.list_licenses(client)


@router.post("", response_model=LicenseRecord, status_code=http_status.HTTP_201_CREATED)
async def create_license(
    license_input: LicenseCreate,
    _: AdminAuth,
    client: AdminClient,
) -> LicenseRecord:
    return await licenses.create_license(client, license_input)


@router.get("/{license_id}", response_model=LicenseRecord)
async def get_license(
    license_id: UUID,
    _: AdminAuth,
    client: AdminClient,
) -> LicenseRecord:
    return await licenses.get_license(client, license_id)


@router.patch("/{license_id}", response_model=LicenseRecord)
async def update_license(
    license_id: UUID,
    license_input: LicensePatch,
    _: AdminAuth,
    client: AdminClient,
) -> LicenseRecord:
    return await licenses.update_license(client, license_id, license_input)


@router.delete("/{license_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_license(
    license_id: UUID,
    _: AdminAuth,
    client: AdminClient,
) -> Response:
    return await licenses.delete_license(client, license_id)
