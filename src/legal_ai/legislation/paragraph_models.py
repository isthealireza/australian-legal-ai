"""Strict immutable models for deterministic legislation paragraphs."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from .models import LegislationStructureDiagnostic
from .subsection_models import (
    LegislationSubstructureDiagnostic,
    SubstructuredLegislationBlock,
)


class ParagraphRole(StrEnum):
    """The complete bounded role set recognised by Sprint 1.3B2B1."""

    NONE = "none"
    PARAGRAPH = "paragraph"
    SCHEDULE_PARAGRAPH = "schedule_paragraph"


class LegislationParagraphDiagnosticCode(StrEnum):
    """Bounded reasons emitted by the paragraph recogniser."""

    MARKER_OUTSIDE_PROVISION = "marker_outside_provision"
    UNSUPPORTED_MARKER = "unsupported_marker"
    AMBIGUOUS_ROMAN_MARKER = "ambiguous_roman_marker"


class LegislationParagraphModel(BaseModel):
    """Shared strict and immutable model configuration."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ParagraphStructuredLegislationBlock(SubstructuredLegislationBlock):
    """One B2A block plus its bounded paragraph classification."""

    paragraph_role: ParagraphRole
    paragraph_identifier: str | None
    paragraph_text: str | None
    paragraph_parent_ordinal: int | None = Field(strict=True, ge=0)
    final_effective_content_container_ordinal: int | None = Field(strict=True, ge=0)


class LegislationParagraphDiagnostic(LegislationParagraphModel):
    """A concise, source-linked paragraph recognition decision."""

    global_block_ordinal: int = Field(strict=True, ge=0)
    source_locator: str
    code: LegislationParagraphDiagnosticCode


class ParagraphStructuredLegislationDocument(LegislationParagraphModel):
    """Ordered, lossless B2A structure enriched with bounded paragraphs."""

    artifact_sha256: str
    package_identifier: str | None
    package_title: str | None
    language: str | None
    blocks: tuple[ParagraphStructuredLegislationBlock, ...]
    structure_diagnostics: tuple[LegislationStructureDiagnostic, ...]
    substructure_diagnostics: tuple[LegislationSubstructureDiagnostic, ...]
    diagnostics: tuple[LegislationParagraphDiagnostic, ...]
