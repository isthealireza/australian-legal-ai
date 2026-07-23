from __future__ import annotations

from typing import cast

import pytest
from pydantic import ValidationError

from legal_ai.legislation import (
    LegislationParagraphDiagnosticCode,
    LegislationParagraphError,
    LegislationParagraphValidationError,
    ParagraphRole,
    ParagraphStructuredLegislationBlock,
    ParagraphStructuredLegislationDocument,
    StructuralRole,
    SubstructuredLegislationDocument,
    SubstructureRole,
    structure_legislation,
    structure_legislation_paragraphs,
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
        package_identifier="urn:test:invented-paragraphs",
        package_title="Invented Paragraphs",
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


def _substructured(*blocks: EpubTextBlock) -> SubstructuredLegislationDocument:
    structured = structure_legislation(_source_document(tuple(blocks)))
    return structure_legislation_subsections(structured)


def _transform(*blocks: EpubTextBlock) -> ParagraphStructuredLegislationDocument:
    return structure_legislation_paragraphs(_substructured(*blocks))


def test_unambiguous_marker_under_section_becomes_paragraph() -> None:
    result = _transform(
        _heading("6 Invented section", 0),
        _paragraph("(a) Invented paragraph text.", 1),
    )

    paragraph = result.blocks[1]
    assert paragraph.paragraph_role is ParagraphRole.PARAGRAPH
    assert paragraph.paragraph_identifier == "a"
    assert paragraph.paragraph_text == "Invented paragraph text."
    assert paragraph.paragraph_parent_ordinal == 0
    assert paragraph.effective_content_container_ordinal == 0
    assert paragraph.final_effective_content_container_ordinal == 1


def test_body_after_paragraph_attaches_to_active_paragraph() -> None:
    result = _transform(
        _heading("6 Invented section", 0),
        _paragraph("Body before.", 1),
        _paragraph("(a) First paragraph.", 2),
        _paragraph("Body after.", 3),
        _paragraph("(b) Second paragraph.", 4),
        _block("List body.", ordinal=5, kind="list_item", tag="li"),
    )

    assert [block.final_effective_content_container_ordinal for block in result.blocks] == [
        0,
        0,
        2,
        2,
        4,
        4,
    ]


def test_new_subsection_clears_active_paragraph() -> None:
    result = _transform(
        _heading("6 Invented section", 0),
        _paragraph("(1) First subsection.", 1),
        _paragraph("(a) Active paragraph.", 2),
        _paragraph("(2) Replacement subsection.", 3),
        _paragraph("Body after reset.", 4),
    )

    assert result.blocks[2].paragraph_parent_ordinal == 1
    assert result.blocks[4].final_effective_content_container_ordinal == 3


def test_roman_ambiguous_marker_stays_none_without_clearing_active_paragraph() -> None:
    result = _transform(
        _heading("6 Invented section", 0),
        _paragraph("(a) Active paragraph.", 1),
        _paragraph("(i) Ambiguous marker.", 2, locator="EPUB/body.xhtml#ambiguous"),
        _paragraph("Following body.", 3),
    )

    assert result.blocks[2].paragraph_role is ParagraphRole.NONE
    assert result.blocks[2].final_effective_content_container_ordinal == 1
    assert result.blocks[3].final_effective_content_container_ordinal == 1
    assert result.diagnostics[0].global_block_ordinal == 2
    assert result.diagnostics[0].source_locator == "EPUB/body.xhtml#ambiguous"
    assert result.diagnostics[0].code is LegislationParagraphDiagnosticCode.AMBIGUOUS_ROMAN_MARKER


def test_empty_input_and_all_diagnostic_stages_are_preserved() -> None:
    empty = _substructured()

    empty_result = structure_legislation_paragraphs(empty)

    assert empty_result.blocks == ()
    assert empty_result.structure_diagnostics == ()
    assert empty_result.substructure_diagnostics == ()
    assert empty_result.diagnostics == ()

    source = _source_document(
        (
            _heading("Invented unclassified heading", 0),
            _paragraph("(1) Unsupported subsection outside provision.", 1),
        )
    )
    substructured = structure_legislation_subsections(structure_legislation(source))

    result = structure_legislation_paragraphs(substructured)

    assert result.structure_diagnostics == substructured.structure_diagnostics
    assert result.substructure_diagnostics == substructured.diagnostics


def test_document_and_every_b2a_block_field_are_preserved_one_to_one() -> None:
    source = _source_document(
        (
            _heading("6 Invented section", 7),
            _paragraph("(1) Invented subsection.", 9),
            _paragraph(
                "(a) Meaning: \u201cinvented\u201d\u2014special?",
                12,
                locator="EPUB/body.xhtml#paragraph",
                element_id="paragraph",
                class_names=("alpha", "beta"),
                epub_type="example",
                language="x-invented",
            ),
        ),
        artifact_sha256="b" * 64,
    )
    substructured = structure_legislation_subsections(structure_legislation(source))

    result = structure_legislation_paragraphs(substructured)

    assert result.artifact_sha256 == "b" * 64
    assert result.package_identifier == substructured.package_identifier
    assert result.package_title == substructured.package_title
    assert result.language == substructured.language
    assert len(result.blocks) == len(substructured.blocks) == 3
    for original, transformed in zip(substructured.blocks, result.blocks, strict=True):
        for field, value in original.model_dump().items():
            assert getattr(transformed, field) == value
    paragraph = result.blocks[2]
    assert paragraph.source_locator == "EPUB/body.xhtml#paragraph"
    assert paragraph.source_block_ordinal == 12
    assert paragraph.original_element_id == "paragraph"
    assert paragraph.original_class_names == ("alpha", "beta")
    assert paragraph.original_epub_type == "example"
    assert paragraph.original_language == "x-invented"
    assert paragraph.paragraph_text == "Meaning: \u201cinvented\u201d\u2014special?"


def test_global_order_and_state_continue_across_spine_documents() -> None:
    source = _source_document(
        (_heading("6 Invented section", 4), _paragraph("(a) First.", 8)),
        (_paragraph("Following body.", 2), _paragraph("(j) Third.", 6)),
    )
    substructured = structure_legislation_subsections(structure_legislation(source))

    result = structure_legislation_paragraphs(substructured)

    assert [block.global_ordinal for block in result.blocks] == [0, 1, 2, 3]
    assert [block.source_spine_index for block in result.blocks] == [0, 0, 1, 1]
    assert [block.source_block_ordinal for block in result.blocks] == [4, 8, 2, 6]
    assert result.blocks[2].final_effective_content_container_ordinal == 1
    assert result.blocks[3].paragraph_role is ParagraphRole.PARAGRAPH


def test_repeated_execution_is_identical_and_does_not_mutate_input() -> None:
    substructured = _substructured(
        _heading("6 Invented section", 0),
        _paragraph("(a) Invented paragraph.", 1),
    )
    before = substructured.model_dump_json()

    first = structure_legislation_paragraphs(substructured)
    second = structure_legislation_paragraphs(substructured)

    assert first.model_dump_json() == second.model_dump_json()
    assert substructured.model_dump_json() == before


def test_output_models_are_strict_frozen_and_forbid_extra_fields() -> None:
    result = _transform(
        _heading("6 Invented section", 0),
        _paragraph("(a) Invented paragraph.", 1),
    )

    with pytest.raises(ValidationError):
        result.package_title = "Changed"
    with pytest.raises(ValidationError):
        result.blocks[1].paragraph_text = "Changed"
    with pytest.raises(ValidationError):
        type(result).model_validate({**result.model_dump(), "arbitrary": "metadata"})
    with pytest.raises(ValidationError):
        type(result.blocks[1]).model_validate(
            {**result.blocks[1].model_dump(), "arbitrary": "metadata"}
        )


def test_paragraph_enum_and_output_fields_are_bounded() -> None:
    assert {role.value for role in ParagraphRole} == {
        "none",
        "paragraph",
        "schedule_paragraph",
    }
    assert set(ParagraphStructuredLegislationBlock.model_fields) == {
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
        "paragraph_role",
        "paragraph_identifier",
        "paragraph_text",
        "paragraph_parent_ordinal",
        "final_effective_content_container_ordinal",
    }


def test_public_api_rejects_non_substructured_input_with_typed_error() -> None:
    with pytest.raises(LegislationParagraphValidationError):
        structure_legislation_paragraphs(cast(SubstructuredLegislationDocument, {"blocks": []}))


def test_accidental_malformed_input_error_is_translated_at_public_boundary() -> None:
    malformed = SubstructuredLegislationDocument.model_construct(
        artifact_sha256="a" * 64,
        package_identifier=None,
        package_title=None,
        language=None,
        blocks=cast(tuple[object, ...], None),
        structure_diagnostics=(),
        diagnostics=(),
    )

    with pytest.raises(LegislationParagraphValidationError) as caught:
        structure_legislation_paragraphs(malformed)

    assert isinstance(caught.value.__cause__, TypeError)


def test_validation_error_belongs_to_public_error_hierarchy() -> None:
    assert issubclass(LegislationParagraphValidationError, LegislationParagraphError)


def test_public_models_are_available_from_package_interface() -> None:
    assert (
        ParagraphStructuredLegislationDocument.__name__ == "ParagraphStructuredLegislationDocument"
    )
    assert ParagraphStructuredLegislationBlock.__name__ == "ParagraphStructuredLegislationBlock"


@pytest.mark.parametrize(
    ("text", "identifier", "remaining_text"),
    [
        ("(a) Invented paragraph text", "a", "Invented paragraph text"),
        ("(b) Another paragraph", "b", "Another paragraph"),
        ("(h) Unambiguous paragraph", "h", "Unambiguous paragraph"),
        ("(j) Unambiguous paragraph", "j", "Unambiguous paragraph"),
        ("(aa) Additional paragraph", "aa", "Additional paragraph"),
        ("(ab) Additional paragraph", "ab", "Additional paragraph"),
        ("(ia) Body text.", "ia", "Body text."),
        ("(az) Body text.", "az", "Body text."),
        (
            "(aaa) Meaning: \u201cinvented\u201d\u2014special?",
            "aaa",
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

    paragraph = result.blocks[1]
    assert paragraph.paragraph_role is ParagraphRole.PARAGRAPH
    assert paragraph.paragraph_identifier == identifier
    assert paragraph.paragraph_text == remaining_text
    assert paragraph.paragraph_parent_ordinal == 0
    assert paragraph.final_effective_content_container_ordinal == 1
    assert paragraph.original_normalized_text == text


def test_layout_whitespace_is_normalised_only_for_recognition() -> None:
    text = "(ab)\u00a0 Invented\u00a0text."

    paragraph = _transform(
        _heading("6 Invented section", 0),
        _paragraph(text, 1),
    ).blocks[1]

    assert paragraph.paragraph_identifier == "ab"
    assert paragraph.paragraph_text == "Invented text."
    assert paragraph.original_normalized_text == text


def test_main_paragraph_parent_is_active_subsection_when_present() -> None:
    result = _transform(
        _heading("6 Invented section", 0),
        _paragraph("(1) Invented subsection.", 1),
        _paragraph("(a) Invented paragraph.", 2),
    )

    assert result.blocks[2].paragraph_role is ParagraphRole.PARAGRAPH
    assert result.blocks[2].paragraph_parent_ordinal == 1
    assert result.blocks[2].effective_content_container_ordinal == 1


@pytest.mark.parametrize("with_subclause", [False, True])
def test_schedule_paragraph_parent_is_deepest_schedule_provision(
    with_subclause: bool,
) -> None:
    blocks = [
        _heading("Schedule 1\u2014Invented", 0),
        _heading("6 Invented clause", 1),
    ]
    if with_subclause:
        blocks.append(_paragraph("(1) Invented subclause.", 2))
    marker_ordinal = len(blocks)
    blocks.append(_paragraph("(a) Invented Schedule paragraph.", marker_ordinal))

    result = _transform(*blocks)

    paragraph = result.blocks[-1]
    assert paragraph.paragraph_role is ParagraphRole.SCHEDULE_PARAGRAPH
    assert paragraph.paragraph_parent_ordinal == (2 if with_subclause else 1)
    assert paragraph.final_effective_content_container_ordinal == marker_ordinal


def test_schedule_content_tracks_each_active_schedule_paragraph() -> None:
    result = _transform(
        _heading("Schedule 1\u2014Invented", 0),
        _heading("6 Invented clause", 1),
        _paragraph("Body before.", 2),
        _paragraph("(a) First Schedule paragraph.", 3),
        _paragraph("Body after first.", 4),
        _paragraph("(b) Second Schedule paragraph.", 5),
        _paragraph("Body after second.", 6),
    )

    assert [
        result.blocks[index].final_effective_content_container_ordinal for index in (2, 3, 4, 5, 6)
    ] == [1, 3, 3, 5, 5]


def test_mixed_non_roman_identifier_is_recognised_under_schedule_clause() -> None:
    result = _transform(
        _heading("Schedule 1\u2014Invented", 0),
        _heading("6 Invented clause", 1),
        _paragraph("(ia) Body text.", 2),
    )

    paragraph = result.blocks[2]
    assert paragraph.paragraph_role is ParagraphRole.SCHEDULE_PARAGRAPH
    assert paragraph.paragraph_identifier == "ia"
    assert paragraph.paragraph_parent_ordinal == 1


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
def test_supported_marker_outside_valid_provision_remains_none(
    container_heading: str | None,
) -> None:
    blocks = (
        (_heading(container_heading, 0), _paragraph("(a) Marker.", 1))
        if container_heading is not None
        else (_paragraph("(a) Marker.", 0),)
    )

    result = _transform(*blocks)

    marker = result.blocks[-1]
    assert marker.paragraph_role is ParagraphRole.NONE
    assert marker.paragraph_identifier is None
    assert marker.paragraph_text is None
    assert marker.paragraph_parent_ordinal is None
    assert (
        result.diagnostics[-1].code is LegislationParagraphDiagnosticCode.MARKER_OUTSIDE_PROVISION
    )


@pytest.mark.parametrize(
    "schedule_container_heading",
    [
        "Part 1\u2014Invented",
        "Division 1\u2014Invented",
        "Subdivision A\u2014Invented",
    ],
)
def test_marker_under_schedule_hierarchy_without_clause_remains_outside_provision(
    schedule_container_heading: str,
) -> None:
    marker_text = "(a) Body text."
    result = _transform(
        _heading("Schedule 1\u2014Invented", 0),
        _heading(schedule_container_heading, 1),
        _paragraph(marker_text, 2),
    )

    assert len(result.blocks) == 3
    assert sum(block.original_normalized_text == marker_text for block in result.blocks) == 1
    marker = result.blocks[2]
    assert marker.paragraph_role is ParagraphRole.NONE
    assert marker.paragraph_identifier is None
    assert marker.paragraph_text is None
    assert marker.paragraph_parent_ordinal is None
    assert marker.final_effective_content_container_ordinal == 1
    assert marker.final_effective_content_container_ordinal != marker.global_ordinal
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].global_block_ordinal == 2
    assert result.diagnostics[0].code is LegislationParagraphDiagnosticCode.MARKER_OUTSIDE_PROVISION


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
        ("table_header", "th"),
        ("table_cell", "td"),
        ("definition_term", "dt"),
        ("definition_description", "dd"),
        ("blockquote", "blockquote"),
        ("preformatted", "pre"),
        ("caption", "caption"),
    ],
)
def test_only_ordinary_paragraph_blocks_can_become_legal_paragraphs(
    kind: EpubBlockKind,
    tag: str,
) -> None:
    result = _transform(
        _heading("6 Invented section", 0),
        _block("(a) Marker.", ordinal=1, kind=kind, tag=tag),
    )

    assert result.blocks[1].paragraph_role is ParagraphRole.NONE
    assert result.blocks[1].role is (
        StructuralRole.UNCLASSIFIED_HEADING if kind == "heading" else StructuralRole.CONTENT
    )


@pytest.mark.parametrize(
    "text",
    [
        "(01) Numeric marker",
        "(aA) Mixed case",
        "(aaaa) Excessive length",
        "[a] Brackets",
        "a) Missing opening parenthesis",
        "(a Missing closing parenthesis",
        "(a)",
        "(a)    ",
        "((a)) Nested marker",
        "prefix (a) Text",
    ],
)
def test_other_malformed_markers_are_not_partially_classified(text: str) -> None:
    result = _transform(_heading("6 Invented section", 0), _paragraph(text, 1))

    marker = result.blocks[1]
    assert marker.paragraph_role is ParagraphRole.NONE
    assert marker.paragraph_identifier is None
    assert marker.paragraph_text is None
    assert marker.paragraph_parent_ordinal is None
    assert (
        marker.final_effective_content_container_ordinal
        == marker.effective_content_container_ordinal
    )


@pytest.mark.parametrize("text", ["(A) Body text.", "(a1) Body text."])
def test_unsupported_alphabetic_marker_uses_existing_diagnostic(text: str) -> None:
    result = _transform(_heading("6 Invented section", 0), _paragraph(text, 1))

    marker = result.blocks[1]
    assert marker.substructure_role is SubstructureRole.NONE
    assert marker.paragraph_role is ParagraphRole.NONE
    assert marker.paragraph_identifier is None
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code is LegislationParagraphDiagnosticCode.UNSUPPORTED_MARKER


@pytest.mark.parametrize("text", ["(a)Text", "(a)-Text"])
def test_marker_requires_whitespace_before_body_text(text: str) -> None:
    result = _transform(_heading("6 Invented section", 0), _paragraph(text, 1))

    marker = result.blocks[1]
    assert marker.paragraph_role is ParagraphRole.NONE
    assert marker.paragraph_identifier is None
    assert marker.paragraph_text is None
    assert marker.paragraph_parent_ordinal is None
    assert marker.final_effective_content_container_ordinal == 0
    assert result.diagnostics == ()


def test_existing_b2a_numeric_subsection_is_preserved_without_paragraph_role() -> None:
    result = _transform(
        _heading("6 Invented section", 0),
        _paragraph("(1) Numeric subsection", 1),
    )

    subsection = result.blocks[1]
    assert subsection.substructure_role is SubstructureRole.SUBSECTION
    assert subsection.substructure_identifier == "1"
    assert subsection.substructure_text == "Numeric subsection"
    assert subsection.paragraph_role is ParagraphRole.NONE
    assert subsection.paragraph_identifier is None
    assert subsection.paragraph_text is None
    assert subsection.paragraph_parent_ordinal is None
    assert subsection.effective_content_container_ordinal == 1
    assert subsection.final_effective_content_container_ordinal == 1
    assert result.diagnostics == ()


@pytest.mark.parametrize(
    "identifier",
    [
        "c",
        "d",
        "i",
        "ii",
        "iii",
        "iv",
        "v",
        "vi",
        "vii",
        "viii",
        "ix",
        "x",
        "xi",
        "xiv",
        "xv",
        "xx",
        "m",
        "mix",
    ],
)
def test_roman_like_identifier_remains_unclassified_without_replacing_active_paragraph(
    identifier: str,
) -> None:
    result = _transform(
        _heading("6 Invented section", 0),
        _paragraph("(a) Active paragraph.", 1),
        _paragraph(f"({identifier}) Body text.", 2),
        _paragraph("Following body.", 3),
    )

    marker = result.blocks[2]
    assert result.blocks[1].paragraph_role is ParagraphRole.PARAGRAPH
    assert marker.substructure_role is SubstructureRole.NONE
    assert marker.paragraph_role is ParagraphRole.NONE
    assert marker.paragraph_identifier is None
    assert marker.paragraph_text is None
    assert marker.paragraph_parent_ordinal is None
    assert marker.final_effective_content_container_ordinal == 1
    assert result.blocks[3].final_effective_content_container_ordinal == 1
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].global_block_ordinal == 2
    assert result.diagnostics[0].code is LegislationParagraphDiagnosticCode.AMBIGUOUS_ROMAN_MARKER


def test_sequence_does_not_disambiguate_roman_marker() -> None:
    result = _transform(
        _heading("6 Invented section", 0),
        _paragraph("(h) Active paragraph.", 1),
        _paragraph("(i) Still ambiguous.", 2),
        _paragraph("Following body.", 3),
    )

    assert result.blocks[2].paragraph_role is ParagraphRole.NONE
    assert result.blocks[3].final_effective_content_container_ordinal == 1


def test_diagnostics_are_deterministic_bounded_and_source_linked() -> None:
    substructured = _substructured(
        _paragraph("(a) Outside.", 0, locator="EPUB/body.xhtml#outside"),
        _heading("6 Invented section", 1),
        _paragraph("(i) Ambiguous.", 2, locator="EPUB/body.xhtml#ambiguous"),
        _paragraph("(A) Unsupported.", 3, locator="EPUB/body.xhtml#unsupported"),
        _paragraph("Ordinary body.", 4),
    )

    first = structure_legislation_paragraphs(substructured)
    second = structure_legislation_paragraphs(substructured)

    assert first.diagnostics == second.diagnostics
    assert len(first.diagnostics) == 3 <= len(first.blocks)
    assert [diagnostic.global_block_ordinal for diagnostic in first.diagnostics] == [0, 2, 3]
    assert [diagnostic.source_locator for diagnostic in first.diagnostics] == [
        "EPUB/body.xhtml#outside",
        "EPUB/body.xhtml#ambiguous",
        "EPUB/body.xhtml#unsupported",
    ]
    assert "Outside" not in first.diagnostics[0].model_dump_json()
    assert "Ambiguous" not in first.diagnostics[1].model_dump_json()
    assert "Unsupported" not in first.diagnostics[2].model_dump_json()


@pytest.mark.parametrize(
    "reset_block",
    [
        _heading("Chapter 2\u2014Replacement", 2),
        _heading("Part 2\u2014Replacement", 2),
        _heading("Division 2\u2014Replacement", 2),
        _heading("Subdivision B\u2014Replacement", 2),
        _heading("7 Replacement section", 2),
        _paragraph("(1) Replacement subsection.", 2),
        _heading("Schedule 1\u2014Replacement", 2),
    ],
)
def test_main_legal_boundaries_clear_active_paragraph(
    reset_block: EpubTextBlock,
) -> None:
    result = _transform(
        _heading("6 Invented section", 0),
        _paragraph("(a) Active paragraph.", 1),
        reset_block,
        _paragraph("Body after reset.", 3),
    )

    assert result.blocks[3].final_effective_content_container_ordinal == 2


def test_endnotes_permanently_clears_main_paragraph_state() -> None:
    result = _transform(
        _heading("6 Invented section", 0),
        _paragraph("(a) Active paragraph.", 1),
        _heading("Endnotes", 2),
        _heading("Chapter 9\u2014History", 3),
        _paragraph("(b) Historical marker.", 4),
        _paragraph("Historical body.", 5),
    )

    assert result.blocks[2].final_effective_content_container_ordinal == 2
    assert all(
        block.final_effective_content_container_ordinal is None for block in result.blocks[3:]
    )
    assert result.blocks[4].paragraph_role is ParagraphRole.NONE


@pytest.mark.parametrize(
    "reset_block",
    [
        _heading("Schedule 2\u2014Replacement", 3),
        _heading("Part 2\u2014Replacement", 3),
        _heading("Division 2\u2014Replacement", 3),
        _heading("Subdivision B\u2014Replacement", 3),
        _heading("7 Replacement clause", 3),
        _paragraph("(1) Replacement subclause.", 3),
        _heading("Chapter 2\u2014Main body", 3),
    ],
)
def test_schedule_legal_boundaries_clear_active_schedule_paragraph(
    reset_block: EpubTextBlock,
) -> None:
    result = _transform(
        _heading("Schedule 1\u2014Invented", 0),
        _heading("6 Invented clause", 1),
        _paragraph("(a) Active Schedule paragraph.", 2),
        reset_block,
        _paragraph("Body after reset.", 4),
    )

    assert result.blocks[4].final_effective_content_container_ordinal == 3


def test_endnotes_clears_schedule_paragraph_state() -> None:
    result = _transform(
        _heading("Schedule 1\u2014Invented", 0),
        _heading("6 Invented clause", 1),
        _paragraph("(a) Active Schedule paragraph.", 2),
        _heading("Endnotes", 3),
        _paragraph("Body after endnotes.", 4),
    )

    assert result.blocks[4].final_effective_content_container_ordinal is None


@pytest.mark.parametrize("schedule", [False, True])
def test_unsupported_marker_does_not_clear_active_paragraph(schedule: bool) -> None:
    provision = (
        (_heading("Schedule 1\u2014Invented", 0), _heading("6 Invented clause", 1))
        if schedule
        else (_heading("6 Invented section", 0),)
    )
    active_ordinal = len(provision)
    result = _transform(
        *provision,
        _paragraph("(a) Active paragraph.", active_ordinal),
        _paragraph("(A) Unsupported marker.", active_ordinal + 1),
        _paragraph("Following body.", active_ordinal + 2),
    )

    expected_role = ParagraphRole.SCHEDULE_PARAGRAPH if schedule else ParagraphRole.PARAGRAPH
    assert result.blocks[active_ordinal].paragraph_role is expected_role
    assert result.blocks[-2].paragraph_role is ParagraphRole.NONE
    assert result.blocks[-2].final_effective_content_container_ordinal == active_ordinal
    assert result.blocks[-1].final_effective_content_container_ordinal == active_ordinal


def test_unclassified_heading_does_not_clear_active_paragraph() -> None:
    result = _transform(
        _heading("6 Invented section", 0),
        _paragraph("(a) Active paragraph.", 1),
        _heading("Invented unclassified heading", 2),
        _paragraph("Following body.", 3),
    )

    assert result.blocks[2].role is StructuralRole.UNCLASSIFIED_HEADING
    assert result.blocks[2].final_effective_content_container_ordinal == 0
    assert result.blocks[3].final_effective_content_container_ordinal == 1


@pytest.mark.parametrize(
    "texts",
    [
        ("(a) First.", "(a) Repeated."),
        ("(a) First.", "(e) Gap."),
        ("(aaa) Largest supported.", "(b) Lower later."),
    ],
)
def test_identifiers_need_not_be_unique_or_sequential(texts: tuple[str, str]) -> None:
    result = _transform(
        _heading("6 Invented section", 0),
        _paragraph(texts[0], 1),
        _paragraph(texts[1], 2),
    )

    assert [block.paragraph_role for block in result.blocks[1:]] == [
        ParagraphRole.PARAGRAPH,
        ParagraphRole.PARAGRAPH,
    ]
