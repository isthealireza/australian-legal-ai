"""Strict models for the Federal Register fields used by Sprint 1.1."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
)

FederalRegisterId = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[A-Z]\d{4}[A-Z]\d{5}$"),
]


def _validate_timestamp(value: str) -> str:
    if len(value) >= 6 and value[-6] in "+-":
        offset_hours = int(value[-5:-3])
        offset_minutes = int(value[-2:])
        if offset_hours > 23 or offset_minutes > 59:
            raise ValueError("Federal Register timestamp has an invalid UTC offset")
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


FederalRegisterTimestamp = Annotated[
    str,
    StringConstraints(
        strict=True,
        pattern=(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
            r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$"
        ),
    ),
    AfterValidator(_validate_timestamp),
]


class FederalRegisterModel(BaseModel):
    """Compatibility policy shared by the selected upstream models."""

    model_config = ConfigDict(extra="allow", strict=True, populate_by_name=True)


class TitleMetadata(FederalRegisterModel):
    """Provenance fields required from a Federal Register title."""

    title_id: FederalRegisterId = Field(alias="id")
    name: str
    making_date: FederalRegisterTimestamp = Field(alias="makingDate")
    collection: Literal["Act"]
    is_principal: bool = Field(alias="isPrincipal")
    is_in_force: bool = Field(alias="isInForce")
    status: Literal["InForce", "Ceased", "Repealed", "NeverEffective"]
    has_commenced_unincorporated_amendments: bool = Field(
        alias="hasCommencedUnincorporatedAmendments"
    )


class VersionMetadata(FederalRegisterModel):
    """Provenance fields required from a registered title version."""

    title_id: FederalRegisterId = Field(alias="titleId")
    start: FederalRegisterTimestamp
    end: FederalRegisterTimestamp | None
    is_current: bool = Field(alias="isCurrent")
    is_latest: bool = Field(alias="isLatest")
    name: str
    status: Literal["InForce", "Ceased", "Repealed", "NeverEffective"]
    register_id: FederalRegisterId = Field(alias="registerId")
    registered_at: FederalRegisterTimestamp = Field(alias="registeredAt")
    compilation_number: str = Field(alias="compilationNumber")
    has_unincorporated_amendments: bool = Field(alias="hasUnincorporatedAmendments")


class VersionListResponse(FederalRegisterModel):
    """Selected OData collection response for registered versions."""

    value: list[VersionMetadata]
    next_link: str | None = Field(default=None, alias="@odata.nextLink")


class DocumentMetadata(FederalRegisterModel):
    """Provenance and rendition fields required for document discovery."""

    title_id: FederalRegisterId = Field(alias="titleId")
    start: FederalRegisterTimestamp
    rectification_version_number: int = Field(alias="rectificationVersionNumber")
    type: Literal[
        "Primary",
        "ES",
        "SupportingMaterial",
        "IncorporatedByReference",
        "SupplementaryES",
    ]
    unique_type_number: int = Field(alias="uniqueTypeNumber")
    volume_number: int = Field(alias="volumeNumber")
    format: Literal["Word", "Pdf", "Epub", "NameOnly"]
    compilation_number: str = Field(alias="compilationNumber")
    register_id: FederalRegisterId = Field(alias="registerId")
    extension: str | None
    page_count: int | None = Field(alias="pageCount")
    size_in_bytes: int | None = Field(alias="sizeInBytes")
    is_authorised: bool = Field(alias="isAuthorised")
    contents: str | None


class DocumentListResponse(FederalRegisterModel):
    """Selected OData collection response for document metadata."""

    value: list[DocumentMetadata]
    next_link: str | None = Field(default=None, alias="@odata.nextLink")
