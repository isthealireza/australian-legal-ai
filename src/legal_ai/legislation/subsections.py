"""Pure deterministic subsection and Schedule subclause recognition."""

import re
from dataclasses import dataclass

from .models import StructuralRole, StructuredLegislationBlock, StructuredLegislationDocument
from .subsection_models import (
    LegislationSubstructureDiagnostic,
    LegislationSubstructureDiagnosticCode,
    SubstructuredLegislationBlock,
    SubstructuredLegislationDocument,
    SubstructureRole,
)

_SUBSTRUCTURE_PATTERN = re.compile(
    r"^\((?P<identifier>[1-9][0-9]{0,2}[A-Z]{0,2})\) "
    r"(?P<text>\S(?:.*\S)?)$"
)
_MARKER_LIKE_PATTERN = re.compile(r"^\([^)]*\)(?:\s|$)")

_MAIN_SUBSECTION_RESET_ROLES = frozenset(
    {
        StructuralRole.CHAPTER_HEADING,
        StructuralRole.PART_HEADING,
        StructuralRole.DIVISION_HEADING,
        StructuralRole.SUBDIVISION_HEADING,
        StructuralRole.SECTION_HEADING,
        StructuralRole.SCHEDULE_HEADING,
    }
)
_SCHEDULE_SUBCLAUSE_RESET_ROLES = frozenset(
    {
        StructuralRole.CHAPTER_HEADING,
        StructuralRole.SCHEDULE_HEADING,
        StructuralRole.SCHEDULE_PART_HEADING,
        StructuralRole.SCHEDULE_DIVISION_HEADING,
        StructuralRole.SCHEDULE_SUBDIVISION_HEADING,
        StructuralRole.SCHEDULE_CLAUSE_HEADING,
    }
)


class LegislationSubstructureError(Exception):
    """Base error for the public legislation-substructure boundary."""


class LegislationSubstructureValidationError(LegislationSubstructureError):
    """The supplied B1 document could not be substructured safely."""


@dataclass(frozen=True, slots=True)
class _RecognisedSubstructure:
    identifier: str
    text: str


@dataclass(slots=True)
class _SubstructureState:
    subsection: int | None = None
    schedule_subclause: int | None = None
    in_endnotes: bool = False

    def apply_structural_reset(self, role: StructuralRole) -> None:
        if role is StructuralRole.ENDNOTES_HEADING:
            self.subsection = None
            self.schedule_subclause = None
            self.in_endnotes = True
            return
        if role in _MAIN_SUBSECTION_RESET_ROLES:
            self.subsection = None
        if role in _SCHEDULE_SUBCLAUSE_RESET_ROLES:
            self.schedule_subclause = None


def structure_legislation_subsections(
    document: StructuredLegislationDocument,
) -> SubstructuredLegislationDocument:
    """Enrich an existing B1 document without I/O or input mutation."""

    if not isinstance(document, StructuredLegislationDocument):
        raise LegislationSubstructureValidationError(
            "legislation substructure input must be a StructuredLegislationDocument"
        )
    try:
        return _structure_subsections(document)
    except LegislationSubstructureError:
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
        raise LegislationSubstructureValidationError(
            "legislation substructure could not be classified safely"
        ) from exc


def _structure_subsections(
    document: StructuredLegislationDocument,
) -> SubstructuredLegislationDocument:
    state = _SubstructureState()
    source_blocks = {block.global_ordinal: block for block in document.blocks}
    blocks: list[SubstructuredLegislationBlock] = []
    diagnostics: list[LegislationSubstructureDiagnostic] = []

    for source in document.blocks:
        state.apply_structural_reset(source.role)
        container_role = _active_container_role(source, source_blocks)
        recognised = _recognise_candidate(source)
        substructure_role = SubstructureRole.NONE
        substructure_identifier: str | None = None
        substructure_text: str | None = None
        substructure_parent_ordinal: int | None = None
        effective_container = _effective_container(source, container_role, state)

        if recognised is not None and not state.in_endnotes:
            if container_role is StructuralRole.SECTION_HEADING:
                substructure_role = SubstructureRole.SUBSECTION
                state.subsection = source.global_ordinal
                state.schedule_subclause = None
            elif container_role is StructuralRole.SCHEDULE_CLAUSE_HEADING:
                substructure_role = SubstructureRole.SCHEDULE_SUBCLAUSE
                state.schedule_subclause = source.global_ordinal
                state.subsection = None
            else:
                diagnostics.append(
                    _diagnostic(
                        source,
                        LegislationSubstructureDiagnosticCode.MARKER_OUTSIDE_PROVISION,
                    )
                )

            if substructure_role is not SubstructureRole.NONE:
                substructure_identifier = recognised.identifier
                substructure_text = recognised.text
                substructure_parent_ordinal = source.active_container_heading_ordinal
                effective_container = source.global_ordinal
        elif _is_unsupported_marker_in_provision(source, container_role):
            diagnostics.append(
                _diagnostic(
                    source,
                    LegislationSubstructureDiagnosticCode.UNSUPPORTED_MARKER,
                )
            )
        elif _is_supported_marker_outside_provision(source, recognised):
            diagnostics.append(
                _diagnostic(
                    source,
                    LegislationSubstructureDiagnosticCode.MARKER_OUTSIDE_PROVISION,
                )
            )

        blocks.append(
            _copy_block(
                source,
                substructure_role=substructure_role,
                substructure_identifier=substructure_identifier,
                substructure_text=substructure_text,
                substructure_parent_ordinal=substructure_parent_ordinal,
                effective_content_container_ordinal=effective_container,
            )
        )

    return SubstructuredLegislationDocument(
        artifact_sha256=document.artifact_sha256,
        package_identifier=document.package_identifier,
        package_title=document.package_title,
        language=document.language,
        blocks=tuple(blocks),
        structure_diagnostics=document.diagnostics,
        diagnostics=tuple(diagnostics),
    )


def _active_container_role(
    source: StructuredLegislationBlock,
    source_blocks: dict[int, StructuredLegislationBlock],
) -> StructuralRole | None:
    ordinal = source.active_container_heading_ordinal
    if ordinal is None:
        return None
    return source_blocks[ordinal].role


def _recognise_candidate(source: StructuredLegislationBlock) -> _RecognisedSubstructure | None:
    if source.original_kind != "paragraph":
        return None
    match = _SUBSTRUCTURE_PATTERN.fullmatch(
        _normalise_layout_whitespace(source.original_normalized_text)
    )
    if match is None:
        return None
    return _RecognisedSubstructure(match.group("identifier"), match.group("text"))


def _effective_container(
    source: StructuredLegislationBlock,
    container_role: StructuralRole | None,
    state: _SubstructureState,
) -> int | None:
    if source.role is not StructuralRole.CONTENT:
        return source.active_container_heading_ordinal
    if state.in_endnotes:
        return None
    if container_role is StructuralRole.SECTION_HEADING and state.subsection is not None:
        return state.subsection
    if (
        container_role is StructuralRole.SCHEDULE_CLAUSE_HEADING
        and state.schedule_subclause is not None
    ):
        return state.schedule_subclause
    return source.active_container_heading_ordinal


def _is_unsupported_marker_in_provision(
    source: StructuredLegislationBlock,
    container_role: StructuralRole | None,
) -> bool:
    return (
        source.original_kind == "paragraph"
        and container_role
        in {StructuralRole.SECTION_HEADING, StructuralRole.SCHEDULE_CLAUSE_HEADING}
        and _MARKER_LIKE_PATTERN.match(
            _normalise_layout_whitespace(source.original_normalized_text)
        )
        is not None
    )


def _is_supported_marker_outside_provision(
    source: StructuredLegislationBlock,
    recognised: _RecognisedSubstructure | None,
) -> bool:
    return source.original_kind == "paragraph" and recognised is not None


def _diagnostic(
    source: StructuredLegislationBlock,
    code: LegislationSubstructureDiagnosticCode,
) -> LegislationSubstructureDiagnostic:
    return LegislationSubstructureDiagnostic(
        global_block_ordinal=source.global_ordinal,
        source_locator=source.source_locator,
        code=code,
    )


def _normalise_layout_whitespace(value: str) -> str:
    return " ".join(value.split())


def _copy_block(
    source: StructuredLegislationBlock,
    *,
    substructure_role: SubstructureRole,
    substructure_identifier: str | None,
    substructure_text: str | None,
    substructure_parent_ordinal: int | None,
    effective_content_container_ordinal: int | None,
) -> SubstructuredLegislationBlock:
    return SubstructuredLegislationBlock(
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
        substructure_role=substructure_role,
        substructure_identifier=substructure_identifier,
        substructure_text=substructure_text,
        substructure_parent_ordinal=substructure_parent_ordinal,
        effective_content_container_ordinal=effective_content_container_ordinal,
    )
