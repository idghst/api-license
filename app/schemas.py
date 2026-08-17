from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

LicenseStatus = Literal["active", "expiring", "expired", "inactive"]

_KST = ZoneInfo("Asia/Seoul")
_EXPIRING_SOON_DAYS = 30


def calculate_license_status(
    expires_at: date | None, *, today: date | None = None
) -> LicenseStatus:
    """Return the read-only license status from its expiry date in KST."""
    if expires_at is None:
        return "inactive"

    reference_date = today or datetime.now(_KST).date()
    days_until_expiry = (expires_at - reference_date).days
    if days_until_expiry < 0:
        return "expired"
    if days_until_expiry <= _EXPIRING_SOON_DAYS:
        return "expiring"
    return "active"


def _camel_case(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


class AuthMeOut(BaseModel):
    id: str
    email: str | None


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
    partnership_contact: str | None = None
    business_contact: str | None = None
    contract_contact: str | None = None
    affiliate: str | None = None
    license_configuration: str | None = None
    status: LicenseStatus
    memo: str | None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def set_automatic_status(self) -> "LicenseRecord":
        self.status = calculate_license_status(self.expires_at)
        return self


class LicenseList(BaseModel):
    items: list[LicenseRecord]
    count: int


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
    partnership_contact: Annotated[str | None, Field(max_length=200)] = None
    business_contact: Annotated[str | None, Field(max_length=200)] = None
    contract_contact: Annotated[str | None, Field(max_length=200)] = None
    affiliate: Annotated[str | None, Field(max_length=200)] = None
    license_configuration: Annotated[str | None, Field(max_length=5_000)] = None
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
    partnership_contact: Annotated[str | None, Field(max_length=200)] = None
    business_contact: Annotated[str | None, Field(max_length=200)] = None
    contract_contact: Annotated[str | None, Field(max_length=200)] = None
    affiliate: Annotated[str | None, Field(max_length=200)] = None
    license_configuration: Annotated[str | None, Field(max_length=5_000)] = None
    memo: Annotated[str | None, Field(max_length=5_000)] = None

    @model_validator(mode="after")
    def require_at_least_one_change(self) -> "LicensePatch":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        return self
