"""Pure deterministic recognition of bounded Commonwealth legislation structure."""

import re
from dataclasses import dataclass
from enum import StrEnum

from legal_ai.parsing import EpubTextBlock, ParsedEpubDocument

from .errors import LegislationStructureError, LegislationStructureValidationError
from .models import (
    LegislationStructureDiagnostic,
    LegislationStructureDiagnosticCode,
    StructuralRole,
    StructuredLegislationBlock,
    StructuredLegislationDocument,
)

_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_PREFIXED_HEADING_PATTERN = re.compile(
    r"^(?P<label>Chapter|Part|Division|Subdivision|Schedule) "
    r"(?P<identifier>[A-Z0-9-]+) *[\u2013\u2014] *(?P<title>\S(?:.*\S)?)$"
)
_NUMERIC_HYPHENATED_IDENTIFIER_PATTERN = re.compile(r"^[0-9]+(?:-[0-9]+)*(?:[A-Z]{1,3})?$")
_NUMERIC_IDENTIFIER_PATTERN = re.compile(r"^[0-9]+(?:[A-Z]{1,3})?$")
_SUBDIVISION_IDENTIFIER_PATTERN = re.compile(r"^[A-Z]{1,3}$")
_PROVISION_HEADING_PATTERN = re.compile(
    r"^(?P<identifier>[0-9]+[A-Z]{0,3}) (?P<title>\S(?:.*\S)?)$"
)
_CANONICAL_ROMAN_PATTERN = re.compile(
    r"^(?=[MDCLXVI])M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})"
    r"(?:IX|IV|V?I{0,3})$"
)


class _HeadingType(StrEnum):
    CHAPTER = "chapter"
    PART = "part"
    DIVISION = "division"
    SUBDIVISION = "subdivision"
    PROVISION = "provision"
    SCHEDULE = "schedule"
    ENDNOTES = "endnotes"


@dataclass(frozen=True, slots=True)
class _RecognisedHeading:
    heading_type: _HeadingType
    identifier: str | None
    title: str | None


@dataclass(frozen=True, slots=True)
class _AppliedHeading:
    role: StructuralRole
    parent_ordinal: int | None


@dataclass(slots=True)
class _HierarchyState:
    chapter: int | None = None
    part: int | None = None
    division: int | None = None
    subdivision: int | None = None
    section: int | None = None
    schedule: int | None = None
    schedule_part: int | None = None
    schedule_division: int | None = None
    schedule_subdivision: int | None = None
    schedule_clause: int | None = None
    in_endnotes: bool = False

    def clear_main_body(self) -> None:
        self.chapter = None
        self.part = None
        self.division = None
        self.subdivision = None
        self.section = None

    def clear_schedule(self) -> None:
        self.schedule = None
        self.schedule_part = None
        self.schedule_division = None
        self.schedule_subdivision = None
        self.schedule_clause = None

    def clear_all_hierarchy(self) -> None:
        self.clear_main_body()
        self.clear_schedule()

    def active_container(self) -> int | None:
        if self.schedule is not None:
            return _first_present(
                self.schedule_clause,
                self.schedule_subdivision,
                self.schedule_division,
                self.schedule_part,
                self.schedule,
            )
        return _first_present(
            self.section,
            self.subdivision,
            self.division,
            self.part,
            self.chapter,
        )


def structure_legislation(document: ParsedEpubDocument) -> StructuredLegislationDocument:
    """Classify an already parsed EPUB document without I/O or input mutation."""

    if not isinstance(document, ParsedEpubDocument):
        raise LegislationStructureValidationError(
            "legislation structure input must be a ParsedEpubDocument"
        )
    try:
        return _structure_document(document)
    except LegislationStructureError:
        raise
    except (
        IndexError,
        KeyError,
        AttributeError,
        TypeError,
        ValueError,
        RecursionError,
        OverflowError,
    ) as exc:
        raise LegislationStructureValidationError(
            "parsed EPUB structure could not be classified safely"
        ) from exc


def _structure_document(document: ParsedEpubDocument) -> StructuredLegislationDocument:
    state = _HierarchyState()
    blocks: list[StructuredLegislationBlock] = []
    diagnostics: list[LegislationStructureDiagnostic] = []

    for spine_document in document.spine_documents:
        for source_block in spine_document.blocks:
            global_ordinal = len(blocks)
            role = StructuralRole.CONTENT
            identifier: str | None = None
            title: str | None = None
            parent_ordinal: int | None = None
            active_container_ordinal = state.active_container()

            if _is_heading_candidate(source_block):
                recognised = None if state.in_endnotes else _recognise_heading(source_block)
                if recognised is None:
                    role = StructuralRole.UNCLASSIFIED_HEADING
                    diagnostics.append(
                        LegislationStructureDiagnostic(
                            global_block_ordinal=global_ordinal,
                            source_locator=source_block.locator,
                            code=LegislationStructureDiagnosticCode.UNCLASSIFIED_HEADING,
                        )
                    )
                else:
                    applied = _apply_heading(state, recognised, global_ordinal)
                    role = applied.role
                    identifier = recognised.identifier
                    title = recognised.title
                    parent_ordinal = applied.parent_ordinal
                    active_container_ordinal = global_ordinal

            blocks.append(
                _copy_and_classify_block(
                    source_block,
                    source_spine_index=spine_document.spine_index,
                    global_ordinal=global_ordinal,
                    role=role,
                    identifier=identifier,
                    title=title,
                    parent_ordinal=parent_ordinal,
                    active_container_ordinal=active_container_ordinal,
                )
            )

    return StructuredLegislationDocument(
        artifact_sha256=document.artifact_sha256,
        package_identifier=document.package_identifier,
        package_title=document.package_title,
        language=document.language,
        blocks=tuple(blocks),
        diagnostics=tuple(diagnostics),
    )


def _is_heading_candidate(block: EpubTextBlock) -> bool:
    return block.kind == "heading" and block.original_tag in _HEADING_TAGS


def _recognise_heading(block: EpubTextBlock) -> _RecognisedHeading | None:
    text = _normalise_layout_whitespace(block.normalized_text)
    if text == "Endnotes":
        return _RecognisedHeading(_HeadingType.ENDNOTES, None, None)
    if text == "2026 annual overview":
        return None

    prefixed = _PREFIXED_HEADING_PATTERN.fullmatch(text)
    if prefixed is not None:
        label = prefixed.group("label")
        identifier = prefixed.group("identifier")
        title = prefixed.group("title")
        heading_type = _validated_prefixed_heading_type(label, identifier)
        if heading_type is not None:
            return _RecognisedHeading(heading_type, identifier, title)

    provision = _PROVISION_HEADING_PATTERN.fullmatch(text)
    if provision is None:
        return None
    identifier = provision.group("identifier")
    return _RecognisedHeading(
        _HeadingType.PROVISION,
        identifier,
        provision.group("title"),
    )


def _validated_prefixed_heading_type(label: str, identifier: str) -> _HeadingType | None:
    if label == "Chapter" and _NUMERIC_HYPHENATED_IDENTIFIER_PATTERN.fullmatch(identifier):
        return _HeadingType.CHAPTER
    if label == "Part" and (
        _NUMERIC_HYPHENATED_IDENTIFIER_PATTERN.fullmatch(identifier)
        or _is_roman_part_identifier(identifier)
    ):
        return _HeadingType.PART
    if label == "Division" and _NUMERIC_IDENTIFIER_PATTERN.fullmatch(identifier):
        return _HeadingType.DIVISION
    if label == "Subdivision" and _SUBDIVISION_IDENTIFIER_PATTERN.fullmatch(identifier):
        return _HeadingType.SUBDIVISION
    if label == "Schedule" and _NUMERIC_IDENTIFIER_PATTERN.fullmatch(identifier):
        return _HeadingType.SCHEDULE
    return None


def _is_roman_part_identifier(identifier: str) -> bool:
    if _CANONICAL_ROMAN_PATTERN.fullmatch(identifier):
        return True
    for suffix_length in range(1, 4):
        if suffix_length >= len(identifier):
            break
        roman = identifier[:-suffix_length]
        suffix = identifier[-suffix_length:]
        if (
            suffix.isascii()
            and suffix.isalpha()
            and suffix.isupper()
            and _CANONICAL_ROMAN_PATTERN.fullmatch(roman)
        ):
            return True
    return False


def _normalise_layout_whitespace(value: str) -> str:
    return " ".join(value.split())


def _apply_heading(
    state: _HierarchyState,
    heading: _RecognisedHeading,
    ordinal: int,
) -> _AppliedHeading:
    if heading.heading_type is _HeadingType.ENDNOTES:
        state.clear_all_hierarchy()
        state.in_endnotes = True
        return _AppliedHeading(StructuralRole.ENDNOTES_HEADING, None)

    if heading.heading_type is _HeadingType.CHAPTER:
        state.clear_all_hierarchy()
        state.chapter = ordinal
        return _AppliedHeading(StructuralRole.CHAPTER_HEADING, None)

    if heading.heading_type is _HeadingType.SCHEDULE:
        state.clear_all_hierarchy()
        state.schedule = ordinal
        return _AppliedHeading(StructuralRole.SCHEDULE_HEADING, None)

    if state.schedule is not None:
        return _apply_schedule_heading(state, heading, ordinal)
    return _apply_main_body_heading(state, heading, ordinal)


def _apply_main_body_heading(
    state: _HierarchyState,
    heading: _RecognisedHeading,
    ordinal: int,
) -> _AppliedHeading:
    if heading.heading_type is _HeadingType.PART:
        parent = state.chapter
        state.part = ordinal
        state.division = None
        state.subdivision = None
        state.section = None
        return _AppliedHeading(StructuralRole.PART_HEADING, parent)
    if heading.heading_type is _HeadingType.DIVISION:
        parent = _first_present(state.part, state.chapter)
        state.division = ordinal
        state.subdivision = None
        state.section = None
        return _AppliedHeading(StructuralRole.DIVISION_HEADING, parent)
    if heading.heading_type is _HeadingType.SUBDIVISION:
        parent = _first_present(state.division, state.part, state.chapter)
        state.subdivision = ordinal
        state.section = None
        return _AppliedHeading(StructuralRole.SUBDIVISION_HEADING, parent)
    if heading.heading_type is _HeadingType.PROVISION:
        parent = _first_present(
            state.subdivision,
            state.division,
            state.part,
            state.chapter,
        )
        state.section = ordinal
        return _AppliedHeading(StructuralRole.SECTION_HEADING, parent)
    raise LegislationStructureValidationError("unsupported main-body heading transition")


def _apply_schedule_heading(
    state: _HierarchyState,
    heading: _RecognisedHeading,
    ordinal: int,
) -> _AppliedHeading:
    if heading.heading_type is _HeadingType.PART:
        parent = state.schedule
        state.schedule_part = ordinal
        state.schedule_division = None
        state.schedule_subdivision = None
        state.schedule_clause = None
        return _AppliedHeading(StructuralRole.SCHEDULE_PART_HEADING, parent)
    if heading.heading_type is _HeadingType.DIVISION:
        parent = _first_present(state.schedule_part, state.schedule)
        state.schedule_division = ordinal
        state.schedule_subdivision = None
        state.schedule_clause = None
        return _AppliedHeading(StructuralRole.SCHEDULE_DIVISION_HEADING, parent)
    if heading.heading_type is _HeadingType.SUBDIVISION:
        parent = _first_present(
            state.schedule_division,
            state.schedule_part,
            state.schedule,
        )
        state.schedule_subdivision = ordinal
        state.schedule_clause = None
        return _AppliedHeading(StructuralRole.SCHEDULE_SUBDIVISION_HEADING, parent)
    if heading.heading_type is _HeadingType.PROVISION:
        parent = _first_present(
            state.schedule_subdivision,
            state.schedule_division,
            state.schedule_part,
            state.schedule,
        )
        state.schedule_clause = ordinal
        return _AppliedHeading(StructuralRole.SCHEDULE_CLAUSE_HEADING, parent)
    raise LegislationStructureValidationError("unsupported Schedule heading transition")


def _first_present(*ordinals: int | None) -> int | None:
    for ordinal in ordinals:
        if ordinal is not None:
            return ordinal
    return None


def _copy_and_classify_block(
    source: EpubTextBlock,
    *,
    source_spine_index: int,
    global_ordinal: int,
    role: StructuralRole,
    identifier: str | None,
    title: str | None,
    parent_ordinal: int | None,
    active_container_ordinal: int | None,
) -> StructuredLegislationBlock:
    return StructuredLegislationBlock(
        global_ordinal=global_ordinal,
        source_spine_index=source_spine_index,
        source_block_ordinal=source.ordinal,
        source_locator=source.locator,
        original_kind=source.kind,
        original_tag=source.original_tag,
        original_normalized_text=source.normalized_text,
        original_element_id=source.element_id,
        original_class_names=source.class_names,
        original_epub_type=source.epub_type,
        original_language=source.language,
        role=role,
        identifier=identifier,
        title=title,
        parent_heading_ordinal=parent_ordinal,
        active_container_heading_ordinal=active_container_ordinal,
    )
