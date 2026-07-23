"""Strict immutable models for deterministic legislation substructure."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from .models import LegislationStructureDiagnostic, StructuredLegislationBlock


class SubstructureRole(StrEnum):
    """The complete bounded role set recognised by Sprint 1.3B2A."""

    NONE = "none"
    SUBSECTION = "subsection"
    SCHEDULE_SUBCLAUSE = "schedule_subclause"


class LegislationSubstructureDiagnosticCode(StrEnum):
    """Bounded reasons emitted by the substructure recogniser."""

    MARKER_OUTSIDE_PROVISION = "marker_outside_provision"
    UNSUPPORTED_MARKER = "unsupported_marker"


class LegislationSubstructureModel(BaseModel):
    """Shared strict and immutable model configuration."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class SubstructuredLegislationBlock(StructuredLegislationBlock):
    """One B1 block plus its bounded subsection classification."""

    substructure_role: SubstructureRole
    substructure_identifier: str | None
    substructure_text: str | None
    substructure_parent_ordinal: int | None = Field(strict=True, ge=0)
    effective_content_container_ordinal: int | None = Field(strict=True, ge=0)


class LegislationSubstructureDiagnostic(LegislationSubstructureModel):
    """A concise, source-linked substructure recognition decision."""

    global_block_ordinal: int = Field(strict=True, ge=0)
    source_locator: str
    code: LegislationSubstructureDiagnosticCode


class SubstructuredLegislationDocument(LegislationSubstructureModel):
    """Ordered, lossless B1 structure enriched with bounded substructure."""

    artifact_sha256: str
    package_identifier: str | None
    package_title: str | None
    language: str | None
    blocks: tuple[SubstructuredLegislationBlock, ...]
    structure_diagnostics: tuple[LegislationStructureDiagnostic, ...]
    diagnostics: tuple[LegislationSubstructureDiagnostic, ...]
