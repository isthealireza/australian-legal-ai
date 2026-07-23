"""Strict immutable models for deterministic legislation structure recognition."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from legal_ai.parsing.models import EpubBlockKind


class StructuralRole(StrEnum):
    """The complete bounded set of structural roles recognised in Sprint 1.3B1."""

    CONTENT = "content"
    UNCLASSIFIED_HEADING = "unclassified_heading"
    CHAPTER_HEADING = "chapter_heading"
    PART_HEADING = "part_heading"
    DIVISION_HEADING = "division_heading"
    SUBDIVISION_HEADING = "subdivision_heading"
    SECTION_HEADING = "section_heading"
    SCHEDULE_HEADING = "schedule_heading"
    SCHEDULE_PART_HEADING = "schedule_part_heading"
    SCHEDULE_DIVISION_HEADING = "schedule_division_heading"
    SCHEDULE_SUBDIVISION_HEADING = "schedule_subdivision_heading"
    SCHEDULE_CLAUSE_HEADING = "schedule_clause_heading"
    ENDNOTES_HEADING = "endnotes_heading"


class LegislationStructureDiagnosticCode(StrEnum):
    """Bounded diagnostic reasons emitted by the structure recogniser."""

    UNCLASSIFIED_HEADING = "unclassified_heading"


class LegislationStructureModel(BaseModel):
    """Shared strict and immutable model configuration."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class StructuredLegislationBlock(LegislationStructureModel):
    """One source block plus its deterministic structural classification."""

    global_ordinal: int = Field(strict=True, ge=0)
    source_spine_index: int = Field(strict=True, ge=0)
    source_block_ordinal: int = Field(strict=True, ge=0)
    source_locator: str
    original_kind: EpubBlockKind
    original_tag: str
    original_normalized_text: str
    original_element_id: str | None
    original_class_names: tuple[str, ...]
    original_epub_type: str | None
    original_language: str | None
    role: StructuralRole
    identifier: str | None
    title: str | None
    parent_heading_ordinal: int | None = Field(strict=True, ge=0)
    active_container_heading_ordinal: int | None = Field(strict=True, ge=0)


class LegislationStructureDiagnostic(LegislationStructureModel):
    """A bounded, source-linked explanation for an unclassified heading."""

    global_block_ordinal: int = Field(strict=True, ge=0)
    source_locator: str
    code: LegislationStructureDiagnosticCode


class StructuredLegislationDocument(LegislationStructureModel):
    """Flat, ordered, lossless structural view of one parsed EPUB document."""

    artifact_sha256: str
    package_identifier: str | None
    package_title: str | None
    language: str | None
    blocks: tuple[StructuredLegislationBlock, ...]
    diagnostics: tuple[LegislationStructureDiagnostic, ...]
