from __future__ import annotations

from typing import cast

import pytest
from pydantic import ValidationError

from legal_ai.legislation import (
    LegislationSubstructureDiagnosticCode,
    LegislationSubstructureError,
    LegislationSubstructureValidationError,
    StructuralRole,
    StructuredLegislationDocument,
    SubstructuredLegislationBlock,
    SubstructuredLegislationDocument,
    SubstructureRole,
    structure_legislation,
    structure_legislation_subsections,
)
from legal_ai.parsing import EpubSpineDocument, EpubTextBlock, ParsedEpubDocument
from legal_ai.parsing.models import EpubBlockKind


def _block(
    text: str,
    *,
    ordinal: int,
    kind: EpubBlockKind = "heading",
    tag: str = "h2",
    locator: str | None = None,
    element_id: str | None = None,
    class_names: tuple[str, ...] = (),
    epub_type: str | None = None,
    language: str | None = "en-AU",
) -> EpubTextBlock:
    return EpubTextBlock(
        ordinal=ordinal,
        kind=kind,
        original_tag=tag,
        normalized_text=text,
        element_id=element_id,
        locator=locator or f"EPUB/spine.xhtml#block-{ordinal}",
        class_names=class_names,
        epub_type=epub_type,
        language=language,
    )


def _heading(text: str, ordinal: int) -> EpubTextBlock:
    return _block(text, ordinal=ordinal)


def _paragraph(
    text: str,
    ordinal: int,
    *,
    locator: str | None = None,
    element_id: str | None = None,
    class_names: tuple[str, ...] = (),
    epub_type: str | None = None,
    language: str | None = "en-AU",
) -> EpubTextBlock:
    return _block(
        text,
        ordinal=ordinal,
        kind="paragraph",
        tag="p",
        locator=locator,
        element_id=element_id,
        class_names=class_names,
        epub_type=epub_type,
        language=language,
    )


def _source_document(
    *block_groups: tuple[EpubTextBlock, ...],
    artifact_sha256: str = "a" * 64,
) -> ParsedEpubDocument:
    groups = block_groups or ((),)
    return ParsedEpubDocument(
        artifact_sha256=artifact_sha256,
        package_identifier="urn:test:invented-substructure",
        package_title="Invented Substructure",
        language="en-AU",
        spine_documents=tuple(
            EpubSpineDocument(
                spine_index=spine_index,
                href=f"EPUB/spine-{spine_index}.xhtml",
                declared_media_type="application/xhtml+xml",
                document_title=f"Invented spine {spine_index}",
                blocks=blocks,
            )
            for spine_index, blocks in enumerate(groups)
        ),
    )


def _transform(*blocks: EpubTextBlock) -> SubstructuredLegislationDocument:
    structured = structure_legislation(_source_document(tuple(blocks)))
    return structure_legislation_subsections(structured)


def test_empty_input_is_supported() -> None:
    result = structure_legislation_subsections(structure_legislation(_source_document()))

    assert result.blocks == ()
    assert result.structure_diagnostics == ()
    assert result.diagnostics == ()


def test_document_and_source_metadata_are_preserved_one_to_one() -> None:
    source = _source_document(
        (
            _heading("6 Invented section", 7),
            _paragraph(
                "(1A) Invented text.",
                9,
                locator="EPUB/body.xhtml#subsection",
                element_id="subsection",
                class_names=("alpha", "beta"),
                epub_type="example",
                language="x-invented",
            ),
        ),
        artifact_sha256="b" * 64,
    )
    structured = structure_legislation(source)

    result = structure_legislation_subsections(structured)

    assert result.artifact_sha256 == "b" * 64
    assert result.package_identifier == structured.package_identifier
    assert result.package_title == structured.package_title
    assert result.language == structured.language
    assert len(result.blocks) == len(structured.blocks) == 2
    for original, transformed in zip(structured.blocks, result.blocks, strict=True):
        for field, value in original.model_dump().items():
            assert getattr(transformed, field) == value
    subsection = result.blocks[1]
    assert subsection.source_locator == "EPUB/body.xhtml#subsection"
    assert subsection.source_block_ordinal == 9
    assert subsection.original_element_id == "subsection"
    assert subsection.original_class_names == ("alpha", "beta")
    assert subsection.original_epub_type == "example"
    assert subsection.original_language == "x-invented"


def test_global_order_is_preserved_across_spine_documents() -> None:
    source = _source_document(
        (_heading("6 Invented section", 4), _paragraph("(1) First.", 8)),
        (_paragraph("Following body.", 2), _paragraph("(3) Third.", 6)),
    )

    result = structure_legislation_subsections(structure_legislation(source))

    assert [block.global_ordinal for block in result.blocks] == [0, 1, 2, 3]
    assert [block.source_spine_index for block in result.blocks] == [0, 0, 1, 1]
    assert [block.source_block_ordinal for block in result.blocks] == [4, 8, 2, 6]
    assert result.blocks[2].effective_content_container_ordinal == 1
    assert result.blocks[3].substructure_role is SubstructureRole.SUBSECTION


@pytest.mark.parametrize(
    ("text", "identifier", "remaining_text"),
    [
        ("(1) Invented subsection text", "1", "Invented subsection text"),
        ("(2) Another subsection", "2", "Another subsection"),
        ("(12) Larger identifier", "12", "Larger identifier"),
        ("(1A) Suffixed subsection", "1A", "Suffixed subsection"),
        (
            "(12AA) Meaning: \u201cinvented\u201d\u2014special?",
            "12AA",
            "Meaning: \u201cinvented\u201d\u2014special?",
        ),
    ],
)
def test_supported_main_body_markers_are_recognised_exactly(
    text: str,
    identifier: str,
    remaining_text: str,
) -> None:
    result = _transform(_heading("6 Invented section", 0), _paragraph(text, 1))

    subsection = result.blocks[1]
    assert subsection.substructure_role is SubstructureRole.SUBSECTION
    assert subsection.substructure_identifier == identifier
    assert subsection.substructure_text == remaining_text
    assert subsection.substructure_parent_ordinal == 0
    assert subsection.effective_content_container_ordinal == 1
    assert subsection.original_normalized_text == text


def test_layout_whitespace_is_normalised_only_for_recognition() -> None:
    text = "(12AA)\u00a0 Invented\u00a0text."

    subsection = _transform(_heading("6 Invented section", 0), _paragraph(text, 1)).blocks[1]

    assert subsection.substructure_identifier == "12AA"
    assert subsection.substructure_text == "Invented text."
    assert subsection.original_normalized_text == text


def test_content_before_and_after_subsection_uses_the_correct_effective_container() -> None:
    result = _transform(
        _heading("6 Invented section", 0),
        _paragraph("Body before.", 1),
        _paragraph("(1) First subsection.", 2),
        _block("List content.", ordinal=3, kind="list_item", tag="li"),
        _paragraph("(2) Second subsection.", 4),
        _paragraph("Body after second.", 5),
    )

    assert [block.effective_content_container_ordinal for block in result.blocks] == [
        0,
        0,
        2,
        2,
        4,
        4,
    ]


@pytest.mark.parametrize(
    "reset_heading",
    [
        "Chapter 2\u2014Replacement",
        "Part 2\u2014Replacement",
        "Division 2\u2014Replacement",
        "Subdivision B\u2014Replacement",
        "7 Replacement section",
        "Schedule 1\u2014Replacement",
    ],
)
def test_main_hierarchy_headings_clear_active_subsection(reset_heading: str) -> None:
    result = _transform(
        _heading("6 Invented section", 0),
        _paragraph("(1) Active subsection.", 1),
        _heading(reset_heading, 2),
        _paragraph("Body after reset.", 3),
    )

    assert result.blocks[3].effective_content_container_ordinal == 2


def test_endnotes_permanently_clears_subsection_state_and_effective_container() -> None:
    result = _transform(
        _heading("6 Invented section", 0),
        _paragraph("(1) Active subsection.", 1),
        _heading("Endnotes", 2),
        _heading("Chapter 9\u2014History", 3),
        _paragraph("(2) Historical marker.", 4),
        _paragraph("Historical body.", 5),
    )

    assert result.blocks[2].effective_content_container_ordinal == 2
    assert all(block.effective_content_container_ordinal is None for block in result.blocks[3:])
    assert result.blocks[4].substructure_role is SubstructureRole.NONE


def test_schedule_clause_marker_becomes_distinct_schedule_subclause() -> None:
    result = _transform(
        _heading("Schedule 1\u2014Invented", 0),
        _heading("6 Invented clause", 1),
        _paragraph("Body before.", 2),
        _paragraph("(1) First subclause.", 3),
        _paragraph("Body after.", 4),
        _paragraph("(2) Second subclause.", 5),
        _paragraph("Final body.", 6),
    )

    assert result.blocks[3].substructure_role is SubstructureRole.SCHEDULE_SUBCLAUSE
    assert result.blocks[3].substructure_parent_ordinal == 1
    assert result.blocks[3].effective_content_container_ordinal == 3
    assert [result.blocks[index].effective_content_container_ordinal for index in (2, 4, 6)] == [
        1,
        3,
        5,
    ]


@pytest.mark.parametrize(
    "reset_heading",
    [
        "Schedule 2\u2014Replacement",
        "Part 2\u2014Replacement",
        "Division 2\u2014Replacement",
        "Subdivision B\u2014Replacement",
        "7 Replacement clause",
        "Chapter 2\u2014Main body",
    ],
)
def test_schedule_hierarchy_headings_clear_active_subclause(reset_heading: str) -> None:
    result = _transform(
        _heading("Schedule 1\u2014Invented", 0),
        _heading("6 Invented clause", 1),
        _paragraph("(1) Active subclause.", 2),
        _heading(reset_heading, 3),
        _paragraph("Body after reset.", 4),
    )

    assert result.blocks[4].effective_content_container_ordinal == 3


def test_endnotes_clears_schedule_subclause_state() -> None:
    result = _transform(
        _heading("Schedule 1\u2014Invented", 0),
        _heading("6 Invented clause", 1),
        _paragraph("(1) Active subclause.", 2),
        _heading("Endnotes", 3),
        _paragraph("Body after endnotes.", 4),
    )

    assert result.blocks[4].effective_content_container_ordinal is None


@pytest.mark.parametrize(
    "container_heading",
    [
        None,
        "Chapter 1\u2014Invented",
        "Part 1\u2014Invented",
        "Division 1\u2014Invented",
        "Subdivision A\u2014Invented",
        "Schedule 1\u2014Invented",
        "Endnotes",
    ],
)
def test_supported_marker_outside_section_or_schedule_clause_remains_none(
    container_heading: str | None,
) -> None:
    blocks = (
        (_heading(container_heading, 0), _paragraph("(1) Marker.", 1))
        if container_heading is not None
        else (_paragraph("(1) Marker.", 0),)
    )

    result = _transform(*blocks)
    marker = result.blocks[-1]

    assert marker.substructure_role is SubstructureRole.NONE
    assert marker.substructure_identifier is None
    assert marker.substructure_text is None
    assert marker.substructure_parent_ordinal is None
    assert (
        result.diagnostics[-1].code
        is LegislationSubstructureDiagnosticCode.MARKER_OUTSIDE_PROVISION
    )


@pytest.mark.parametrize(
    ("kind", "tag"),
    [
        ("heading", "h1"),
        ("heading", "h2"),
        ("heading", "h3"),
        ("heading", "h4"),
        ("heading", "h5"),
        ("heading", "h6"),
        ("list_item", "li"),
        ("table_cell", "td"),
        ("definition_term", "dt"),
        ("definition_description", "dd"),
        ("blockquote", "blockquote"),
        ("preformatted", "pre"),
        ("caption", "caption"),
    ],
)
def test_only_paragraph_blocks_can_become_substructures(
    kind: EpubBlockKind,
    tag: str,
) -> None:
    result = _transform(
        _heading("6 Invented section", 0),
        _block("(1) Marker.", ordinal=1, kind=kind, tag=tag),
    )

    assert result.blocks[1].substructure_role is SubstructureRole.NONE
    assert result.blocks[1].role is (
        StructuralRole.UNCLASSIFIED_HEADING if kind == "heading" else StructuralRole.CONTENT
    )


@pytest.mark.parametrize(
    "text",
    [
        "(0) Zero",
        "(01) Leading zero",
        "(000) Leading zero",
        "(1a) Lowercase suffix",
        "(1AAA) Excessive suffix",
        "(1234) Excessive digits",
        "(1.1) Decimal",
        "[1] Brackets",
        "1) Missing opening parenthesis",
        "(1 Missing closing parenthesis",
        "(1)",
        "(1)    ",
        "(a) Paragraph",
        "(i) Ambiguous marker",
        "(A) Alphabetic marker",
        "((1)) Nested marker",
    ],
)
def test_unsupported_markers_are_not_partially_classified(text: str) -> None:
    result = _transform(_heading("6 Invented section", 0), _paragraph(text, 1))

    marker = result.blocks[1]
    assert marker.substructure_role is SubstructureRole.NONE
    assert marker.substructure_identifier is None
    assert marker.substructure_text is None
    assert marker.substructure_parent_ordinal is None
    assert marker.effective_content_container_ordinal == 0


@pytest.mark.parametrize("schedule", [False, True])
def test_unsupported_marker_does_not_clear_active_substructure(schedule: bool) -> None:
    provision = (
        (_heading("Schedule 1\u2014Invented", 0), _heading("6 Invented clause", 1))
        if schedule
        else (_heading("6 Invented section", 0),)
    )
    active_ordinal = len(provision)
    result = _transform(
        *provision,
        _paragraph("(1) Active marker.", active_ordinal),
        _paragraph("(a) Unsupported marker.", active_ordinal + 1),
        _paragraph("Following body.", active_ordinal + 2),
    )

    assert result.blocks[-2].substructure_role is SubstructureRole.NONE
    assert result.blocks[-2].effective_content_container_ordinal == active_ordinal
    assert result.blocks[-1].effective_content_container_ordinal == active_ordinal
    assert result.diagnostics[-1].code is LegislationSubstructureDiagnosticCode.UNSUPPORTED_MARKER


@pytest.mark.parametrize(
    "texts",
    [
        ("(1) First.", "(1) Repeated."),
        ("(1) First.", "(3) Gap."),
        ("(999ZZ) Largest supported.", "(2) Lower later."),
    ],
)
def test_identifiers_need_not_be_unique_or_sequential(texts: tuple[str, str]) -> None:
    result = _transform(
        _heading("6 Invented section", 0),
        _paragraph(texts[0], 1),
        _paragraph(texts[1], 2),
    )

    assert [block.substructure_role for block in result.blocks[1:]] == [
        SubstructureRole.SUBSECTION,
        SubstructureRole.SUBSECTION,
    ]


def test_unclassified_heading_keeps_b1_container_without_clearing_state() -> None:
    result = _transform(
        _heading("6 Invented section", 0),
        _paragraph("(1) Active subsection.", 1),
        _heading("Invented unclassified heading", 2),
        _paragraph("Following body.", 3),
    )

    assert result.blocks[2].role is StructuralRole.UNCLASSIFIED_HEADING
    assert result.blocks[2].effective_content_container_ordinal == 0
    assert result.blocks[3].effective_content_container_ordinal == 1


def test_diagnostics_are_deterministic_bounded_and_source_linked() -> None:
    structured = structure_legislation(
        _source_document(
            (
                _paragraph("(1) Outside.", 0, locator="EPUB/body.xhtml#outside"),
                _heading("6 Invented section", 1),
                _paragraph("(a) Unsupported.", 2, locator="EPUB/body.xhtml#unsupported"),
                _paragraph("Ordinary body.", 3),
            )
        )
    )

    first = structure_legislation_subsections(structured)
    second = structure_legislation_subsections(structured)

    assert first.diagnostics == second.diagnostics
    assert len(first.diagnostics) == 2 <= len(first.blocks)
    assert [diagnostic.global_block_ordinal for diagnostic in first.diagnostics] == [0, 2]
    assert [diagnostic.source_locator for diagnostic in first.diagnostics] == [
        "EPUB/body.xhtml#outside",
        "EPUB/body.xhtml#unsupported",
    ]
    assert "Outside" not in first.diagnostics[0].model_dump_json()
    assert "Unsupported" not in first.diagnostics[1].model_dump_json()


def test_existing_b1_diagnostics_are_preserved_as_a_separate_stage() -> None:
    structured = structure_legislation(
        _source_document((_heading("Invented unclassified heading", 0),))
    )

    result = structure_legislation_subsections(structured)

    assert result.structure_diagnostics == structured.diagnostics
    assert result.structure_diagnostics[0].global_block_ordinal == 0
    assert result.diagnostics == ()


def test_repeated_transformation_has_identical_model_json_and_does_not_mutate_input() -> None:
    structured = structure_legislation(
        _source_document(
            (
                _heading("6 Invented section", 0),
                _paragraph("(1) Invented subsection.", 1),
            )
        )
    )
    before = structured.model_dump_json()

    first = structure_legislation_subsections(structured)
    second = structure_legislation_subsections(structured)

    assert first.model_dump_json() == second.model_dump_json()
    assert structured.model_dump_json() == before


def test_output_models_are_strict_frozen_and_forbid_extra_fields() -> None:
    result = _transform(_heading("6 Invented section", 0), _paragraph("(1) Text.", 1))

    with pytest.raises(ValidationError):
        result.package_title = "Changed"
    with pytest.raises(ValidationError):
        result.blocks[1].substructure_text = "Changed"
    with pytest.raises(ValidationError):
        type(result).model_validate({**result.model_dump(), "arbitrary": "metadata"})
    with pytest.raises(ValidationError):
        type(result.blocks[1]).model_validate(
            {**result.blocks[1].model_dump(), "arbitrary": "metadata"}
        )


def test_substructure_enum_contains_only_authorised_roles() -> None:
    assert {role.value for role in SubstructureRole} == {
        "none",
        "subsection",
        "schedule_subclause",
    }


def test_output_block_contains_no_unrestricted_metadata_or_legal_meaning_fields() -> None:
    assert set(SubstructuredLegislationBlock.model_fields) == {
        "global_ordinal",
        "source_spine_index",
        "source_block_ordinal",
        "source_locator",
        "original_kind",
        "original_tag",
        "original_normalized_text",
        "original_element_id",
        "original_class_names",
        "original_epub_type",
        "original_language",
        "role",
        "identifier",
        "title",
        "parent_heading_ordinal",
        "active_container_heading_ordinal",
        "substructure_role",
        "substructure_identifier",
        "substructure_text",
        "substructure_parent_ordinal",
        "effective_content_container_ordinal",
    }


def test_public_api_rejects_non_structured_input_with_typed_error() -> None:
    with pytest.raises(LegislationSubstructureValidationError):
        structure_legislation_subsections(cast(StructuredLegislationDocument, {"blocks": []}))


def test_accidental_malformed_input_error_is_translated_at_public_boundary() -> None:
    malformed = StructuredLegislationDocument.model_construct(
        artifact_sha256="a" * 64,
        package_identifier=None,
        package_title=None,
        language=None,
        blocks=cast(tuple[object, ...], None),
        diagnostics=(),
    )

    with pytest.raises(LegislationSubstructureValidationError) as caught:
        structure_legislation_subsections(malformed)

    assert isinstance(caught.value.__cause__, TypeError)


def test_validation_error_belongs_to_public_error_hierarchy() -> None:
    assert issubclass(LegislationSubstructureValidationError, LegislationSubstructureError)


def test_public_models_are_available_from_package_interface() -> None:
    assert SubstructuredLegislationDocument.__name__ == "SubstructuredLegislationDocument"
    assert SubstructuredLegislationBlock.__name__ == "SubstructuredLegislationBlock"
