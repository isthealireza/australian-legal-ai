"""Strict immutable models for deterministic EPUB structural extraction."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

PositiveStrictInt = Annotated[int, Field(strict=True, gt=0)]
PositiveStrictFloat = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
EpubBlockKind = Literal[
    "heading",
    "paragraph",
    "list_item",
    "definition_term",
    "definition_description",
    "blockquote",
    "preformatted",
    "caption",
    "table_header",
    "table_cell",
]


class EpubModel(BaseModel):
    """Shared strict and immutable model configuration."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class EpubParseLimits(EpubModel):
    """Caller-selected hard limits applied before or during bounded parsing."""

    maximum_archive_bytes: PositiveStrictInt
    maximum_entry_count: PositiveStrictInt
    maximum_entry_uncompressed_bytes: PositiveStrictInt
    maximum_total_uncompressed_bytes: PositiveStrictInt
    maximum_compression_ratio: PositiveStrictFloat
    maximum_xhtml_block_count: PositiveStrictInt
    maximum_text_characters_per_block: PositiveStrictInt


class EpubTextBlock(EpubModel):
    """One generic structural XHTML text block with an exact source locator."""

    ordinal: int = Field(strict=True, ge=0)
    kind: EpubBlockKind
    original_tag: str
    normalized_text: str
    element_id: str | None
    locator: str
    class_names: tuple[str, ...]
    epub_type: str | None
    language: str | None


class EpubSpineDocument(EpubModel):
    """One XHTML manifest item in exact EPUB spine order."""

    spine_index: int = Field(strict=True, ge=0)
    href: str
    declared_media_type: str
    document_title: str | None
    blocks: tuple[EpubTextBlock, ...]


class ParsedEpubDocument(EpubModel):
    """Deterministic in-memory structural representation of one EPUB artifact."""

    artifact_sha256: str
    package_identifier: str | None
    package_title: str | None
    language: str | None
    spine_documents: tuple[EpubSpineDocument, ...]
