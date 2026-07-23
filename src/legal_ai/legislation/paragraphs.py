"""Pure deterministic unambiguous paragraph recognition."""

import re
from dataclasses import dataclass

from .models import StructuralRole
from .paragraph_models import (
    LegislationParagraphDiagnostic,
    LegislationParagraphDiagnosticCode,
    ParagraphRole,
    ParagraphStructuredLegislationBlock,
    ParagraphStructuredLegislationDocument,
)
from .subsection_models import (
    SubstructuredLegislationBlock,
    SubstructuredLegislationDocument,
    SubstructureRole,
)

_PARAGRAPH_PATTERN = re.compile(r"^\((?P<identifier>[a-z]{1,3})\) (?P<text>\S(?:.*\S)?)$")
_ROMAN_MARKER_PATTERN = re.compile(r"^\((?P<identifier>[ivxlcdm]+)\) (?P<text>\S(?:.*\S)?)$")
_MARKER_LIKE_PATTERN = re.compile(r"^\([^)]*\)(?:\s|$)")
_ROMAN_CHARACTERS = frozenset("ivxlcdm")
_MAIN_PARAGRAPH_RESET_ROLES = frozenset(
    {
        StructuralRole.CHAPTER_HEADING,
        StructuralRole.PART_HEADING,
        StructuralRole.DIVISION_HEADING,
        StructuralRole.SUBDIVISION_HEADING,
        StructuralRole.SECTION_HEADING,
        StructuralRole.SCHEDULE_HEADING,
    }
)
_SCHEDULE_PARAGRAPH_RESET_ROLES = frozenset(
    {
        StructuralRole.CHAPTER_HEADING,
        StructuralRole.SCHEDULE_HEADING,
        StructuralRole.SCHEDULE_PART_HEADING,
        StructuralRole.SCHEDULE_DIVISION_HEADING,
        StructuralRole.SCHEDULE_SUBDIVISION_HEADING,
        StructuralRole.SCHEDULE_CLAUSE_HEADING,
    }
)


class LegislationParagraphError(Exception):
    """Base error for the public legislation-paragraph boundary."""


class LegislationParagraphValidationError(LegislationParagraphError):
    """The supplied B2A document could not be paragraph-structured safely."""


@dataclass(frozen=True, slots=True)
class _RecognisedParagraph:
    identifier: str
    text: str


@dataclass(slots=True)
class _ParagraphState:
    paragraph: int | None = None
    schedule_paragraph: int | None = None
    in_endnotes: bool = False

    def apply_legal_reset(self, source: SubstructuredLegislationBlock) -> None:
        if source.role is StructuralRole.ENDNOTES_HEADING:
            self.paragraph = None
            self.schedule_paragraph = None
            self.in_endnotes = True
            return
        if (
            source.role in _MAIN_PARAGRAPH_RESET_ROLES
            or source.substructure_role is SubstructureRole.SUBSECTION
        ):
            self.paragraph = None
        if (
            source.role in _SCHEDULE_PARAGRAPH_RESET_ROLES
            or source.substructure_role is SubstructureRole.SCHEDULE_SUBCLAUSE
        ):
            self.schedule_paragraph = None


def structure_legislation_paragraphs(
    document: SubstructuredLegislationDocument,
) -> ParagraphStructuredLegislationDocument:
    """Enrich an existing B2A document without I/O or input mutation."""

    if not isinstance(document, SubstructuredLegislationDocument):
        raise LegislationParagraphValidationError(
            "legislation paragraph input must be a SubstructuredLegislationDocument"
        )
    try:
        return _structure_paragraphs(document)
    except LegislationParagraphError:
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
        raise LegislationParagraphValidationError(
            "legislation paragraphs could not be classified safely"
        ) from exc


def _structure_paragraphs(
    document: SubstructuredLegislationDocument,
) -> ParagraphStructuredLegislationDocument:
    state = _ParagraphState()
    source_blocks = {block.global_ordinal: block for block in document.blocks}
    blocks: list[ParagraphStructuredLegislationBlock] = []
    diagnostics: list[LegislationParagraphDiagnostic] = []

    for source in document.blocks:
        state.apply_legal_reset(source)
        recognised = _recognise_candidate(source)
        context = _context_role(source, source_blocks)
        paragraph_role = ParagraphRole.NONE
        paragraph_identifier: str | None = None
        paragraph_text: str | None = None
        paragraph_parent_ordinal: int | None = None
        final_effective_container = _effective_container(source, context, state)

        if recognised is not None:
            if state.in_endnotes or context is None:
                diagnostics.append(
                    _diagnostic(
                        source,
                        LegislationParagraphDiagnosticCode.MARKER_OUTSIDE_PROVISION,
                    )
                )
            else:
                paragraph_role = context
                paragraph_identifier = recognised.identifier
                paragraph_text = recognised.text
                paragraph_parent_ordinal = source.effective_content_container_ordinal
                final_effective_container = source.global_ordinal
                if context is ParagraphRole.PARAGRAPH:
                    state.paragraph = source.global_ordinal
                    state.schedule_paragraph = None
                else:
                    state.schedule_paragraph = source.global_ordinal
                    state.paragraph = None
        elif _is_ambiguous_roman_marker(source):
            diagnostics.append(
                _diagnostic(
                    source,
                    LegislationParagraphDiagnosticCode.AMBIGUOUS_ROMAN_MARKER,
                )
            )
        elif _is_marker_like(source):
            diagnostics.append(
                _diagnostic(
                    source,
                    LegislationParagraphDiagnosticCode.UNSUPPORTED_MARKER,
                )
            )

        blocks.append(
            _copy_block(
                source,
                paragraph_role=paragraph_role,
                paragraph_identifier=paragraph_identifier,
                paragraph_text=paragraph_text,
                paragraph_parent_ordinal=paragraph_parent_ordinal,
                final_effective_content_container_ordinal=final_effective_container,
            )
        )

    return ParagraphStructuredLegislationDocument(
        artifact_sha256=document.artifact_sha256,
        package_identifier=document.package_identifier,
        package_title=document.package_title,
        language=document.language,
        blocks=tuple(blocks),
        structure_diagnostics=document.structure_diagnostics,
        substructure_diagnostics=document.diagnostics,
        diagnostics=tuple(diagnostics),
    )


def _recognise_candidate(source: SubstructuredLegislationBlock) -> _RecognisedParagraph | None:
    if source.original_kind != "paragraph" or source.substructure_role is not SubstructureRole.NONE:
        return None
    match = _PARAGRAPH_PATTERN.fullmatch(
        _normalise_layout_whitespace(source.original_normalized_text)
    )
    if match is None:
        return None
    identifier = match.group("identifier")
    if set(identifier) <= _ROMAN_CHARACTERS:
        return None
    return _RecognisedParagraph(identifier, match.group("text"))


def _context_role(
    source: SubstructuredLegislationBlock,
    source_blocks: dict[int, SubstructuredLegislationBlock],
) -> ParagraphRole | None:
    ordinal = source.effective_content_container_ordinal
    if ordinal is None:
        return None
    container = source_blocks[ordinal]
    if (
        container.role is StructuralRole.SECTION_HEADING
        or container.substructure_role is SubstructureRole.SUBSECTION
    ):
        return ParagraphRole.PARAGRAPH
    if (
        container.role is StructuralRole.SCHEDULE_CLAUSE_HEADING
        or container.substructure_role is SubstructureRole.SCHEDULE_SUBCLAUSE
    ):
        return ParagraphRole.SCHEDULE_PARAGRAPH
    return None


def _is_ambiguous_roman_marker(source: SubstructuredLegislationBlock) -> bool:
    if source.original_kind != "paragraph" or source.substructure_role is not SubstructureRole.NONE:
        return False
    match = _ROMAN_MARKER_PATTERN.fullmatch(
        _normalise_layout_whitespace(source.original_normalized_text)
    )
    return match is not None


def _is_marker_like(source: SubstructuredLegislationBlock) -> bool:
    return (
        source.original_kind == "paragraph"
        and source.substructure_role is SubstructureRole.NONE
        and _MARKER_LIKE_PATTERN.match(
            _normalise_layout_whitespace(source.original_normalized_text)
        )
        is not None
    )


def _diagnostic(
    source: SubstructuredLegislationBlock,
    code: LegislationParagraphDiagnosticCode,
) -> LegislationParagraphDiagnostic:
    return LegislationParagraphDiagnostic(
        global_block_ordinal=source.global_ordinal,
        source_locator=source.source_locator,
        code=code,
    )


def _effective_container(
    source: SubstructuredLegislationBlock,
    context: ParagraphRole | None,
    state: _ParagraphState,
) -> int | None:
    if source.role is not StructuralRole.CONTENT:
        return source.effective_content_container_ordinal
    if source.substructure_role is not SubstructureRole.NONE:
        return source.effective_content_container_ordinal
    if state.in_endnotes:
        return None
    if context is ParagraphRole.PARAGRAPH and state.paragraph is not None:
        return state.paragraph
    if context is ParagraphRole.SCHEDULE_PARAGRAPH and state.schedule_paragraph is not None:
        return state.schedule_paragraph
    return source.effective_content_container_ordinal


def _normalise_layout_whitespace(value: str) -> str:
    return " ".join(value.split())


def _copy_block(
    source: SubstructuredLegislationBlock,
    *,
    paragraph_role: ParagraphRole,
    paragraph_identifier: str | None,
    paragraph_text: str | None,
    paragraph_parent_ordinal: int | None,
    final_effective_content_container_ordinal: int | None,
) -> ParagraphStructuredLegislationBlock:
    return ParagraphStructuredLegislationBlock(
        global_ordinal=source.global_ordinal,
        source_spine_index=source.source_spine_index,
        source_block_ordinal=source.source_block_ordinal,
        source_locator=source.source_locator,
        original_kind=source.original_kind,
        original_tag=source.original_tag,
        original_normalized_text=source.original_normalized_text,
        original_element_id=source.original_element_id,
        original_class_names=source.original_class_names,
        original_epub_type=source.original_epub_type,
        original_language=source.original_language,
        role=source.role,
        identifier=source.identifier,
        title=source.title,
        parent_heading_ordinal=source.parent_heading_ordinal,
        active_container_heading_ordinal=source.active_container_heading_ordinal,
        substructure_role=source.substructure_role,
        substructure_identifier=source.substructure_identifier,
        substructure_text=source.substructure_text,
        substructure_parent_ordinal=source.substructure_parent_ordinal,
        effective_content_container_ordinal=source.effective_content_container_ordinal,
        paragraph_role=paragraph_role,
        paragraph_identifier=paragraph_identifier,
        paragraph_text=paragraph_text,
        paragraph_parent_ordinal=paragraph_parent_ordinal,
        final_effective_content_container_ordinal=final_effective_content_container_ordinal,
    )
