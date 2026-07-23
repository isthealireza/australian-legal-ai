from __future__ import annotations

from typing import cast

import pytest
from pydantic import ValidationError

from legal_ai.legislation import (
    LegislationStructureDiagnosticCode,
    LegislationStructureError,
    LegislationStructureValidationError,
    StructuralRole,
    StructuredLegislationBlock,
    StructuredLegislationDocument,
    structure_legislation,
)
from legal_ai.parsing import EpubSpineDocument, EpubTextBlock, ParsedEpubDocument
from legal_ai.parsing.models import EpubBlockKind


def _block(
    text: str,
    *,
    ordinal: int = 0,
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


def _document(
    *block_groups: tuple[EpubTextBlock, ...],
    artifact_sha256: str = "a" * 64,
) -> ParsedEpubDocument:
    groups = block_groups or ((),)
    return ParsedEpubDocument(
        artifact_sha256=artifact_sha256,
        package_identifier="urn:test:invented-legislation",
        package_title="Invented Legislation",
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


def _structured(*blocks: EpubTextBlock) -> StructuredLegislationDocument:
    return structure_legislation(_document(tuple(blocks)))


def test_empty_structured_input_is_supported() -> None:
    result = structure_legislation(_document())

    assert result.blocks == ()
    assert result.diagnostics == ()


def test_document_and_block_source_metadata_are_preserved_one_to_one() -> None:
    source = _document(
        (
            _block(
                "Invented prose.",
                ordinal=7,
                kind="paragraph",
                tag="p",
                locator="EPUB/body.xhtml#invented",
                element_id="invented",
                class_names=("alpha", "beta"),
                epub_type="example",
                language="x-invented",
            ),
        ),
        artifact_sha256="b" * 64,
    )

    result = structure_legislation(source)

    assert result.artifact_sha256 == "b" * 64
    assert result.package_identifier == source.package_identifier
    assert result.package_title == source.package_title
    assert result.language == source.language
    assert len(result.blocks) == 1
    block = result.blocks[0]
    assert block.global_ordinal == 0
    assert block.source_spine_index == 0
    assert block.source_block_ordinal == 7
    assert block.source_locator == "EPUB/body.xhtml#invented"
    assert block.original_kind == "paragraph"
    assert block.original_tag == "p"
    assert block.original_normalized_text == "Invented prose."
    assert block.original_element_id == "invented"
    assert block.original_class_names == ("alpha", "beta")
    assert block.original_epub_type == "example"
    assert block.original_language == "x-invented"


def test_global_ordinals_follow_exact_block_order_across_spines() -> None:
    source = _document(
        (
            _block("First.", ordinal=4, kind="paragraph", tag="p"),
            _block("Second.", ordinal=9, kind="paragraph", tag="p"),
        ),
        (_block("Third.", ordinal=2, kind="paragraph", tag="p"),),
    )

    result = structure_legislation(source)

    assert [block.global_ordinal for block in result.blocks] == [0, 1, 2]
    assert [block.source_spine_index for block in result.blocks] == [0, 0, 1]
    assert [block.source_block_ordinal for block in result.blocks] == [4, 9, 2]
    assert [block.original_normalized_text for block in result.blocks] == [
        "First.",
        "Second.",
        "Third.",
    ]


@pytest.mark.parametrize("tag", ["h1", "h2", "h3", "h4", "h5", "h6"])
def test_only_supported_xhtml_heading_tags_are_candidates(tag: str) -> None:
    result = _structured(_block("6 Invented title", tag=tag))

    assert result.blocks[0].role is StructuralRole.SECTION_HEADING


@pytest.mark.parametrize(
    ("text", "role", "identifier", "title"),
    [
        ("Chapter 1—Preliminary", StructuralRole.CHAPTER_HEADING, "1", "Preliminary"),
        ("Chapter 2A—Administration", StructuralRole.CHAPTER_HEADING, "2A", "Administration"),
        ("Chapter 2-1–General", StructuralRole.CHAPTER_HEADING, "2-1", "General"),
        ("Part 2—Administration", StructuralRole.PART_HEADING, "2", "Administration"),
        ("Part II—Interpretation", StructuralRole.PART_HEADING, "II", "Interpretation"),
        ("Part IVA—Special rules", StructuralRole.PART_HEADING, "IVA", "Special rules"),
        ("Part IVC—Invented rules", StructuralRole.PART_HEADING, "IVC", "Invented rules"),
        ("Part IVX—Invented cases", StructuralRole.PART_HEADING, "IVX", "Invented cases"),
        ("Part 2-1—Preliminary", StructuralRole.PART_HEADING, "2-1", "Preliminary"),
        ("Part 3A—Special rules", StructuralRole.PART_HEADING, "3A", "Special rules"),
        ("Division 1—Preliminary", StructuralRole.DIVISION_HEADING, "1", "Preliminary"),
        (
            "Division 2A—Special provisions",
            StructuralRole.DIVISION_HEADING,
            "2A",
            "Special provisions",
        ),
        ("Subdivision A—General", StructuralRole.SUBDIVISION_HEADING, "A", "General"),
        ("Subdivision AA—Special cases", StructuralRole.SUBDIVISION_HEADING, "AA", "Special cases"),
        (
            "Schedule 1—General provisions",
            StructuralRole.SCHEDULE_HEADING,
            "1",
            "General provisions",
        ),
        (
            "Schedule 2A–Transitional matters",
            StructuralRole.SCHEDULE_HEADING,
            "2A",
            "Transitional matters",
        ),
    ],
)
def test_supported_prefixed_headings_are_recognised(
    text: str,
    role: StructuralRole,
    identifier: str,
    title: str,
) -> None:
    result = _structured(_block(text))

    block = result.blocks[0]
    assert block.role is role
    assert block.identifier == identifier
    assert block.title == title
    assert block.parent_heading_ordinal is None
    assert block.active_container_heading_ordinal == 0


@pytest.mark.parametrize(
    ("text", "identifier", "title"),
    [
        ("6 Interpretation", "6", "Interpretation"),
        ("6A Application", "6A", "Application"),
        ("6AA Meaning of responsible person", "6AA", "Meaning of responsible person"),
        ("18H Special rule", "18H", "Special rule"),
        ("22EA Notification requirement", "22EA", "Notification requirement"),
        ("999 Example", "999", "Example"),
        ("1000 Example", "1000", "Example"),
        ("1500 Example", "1500", "Example"),
        ("1999 Example", "1999", "Example"),
        ("2000 Example", "2000", "Example"),
        ("2026 Application provision", "2026", "Application provision"),
        ("2999 Example", "2999", "Example"),
        ("3000 Example", "3000", "Example"),
        ("2026A Example", "2026A", "Example"),
        ("12026 annual overview", "12026", "annual overview"),
        ("2026 Annual overview", "2026", "Annual overview"),
        ("2026 annual overview amended", "2026", "annual overview amended"),
    ],
)
def test_supported_main_body_section_headings_are_recognised(
    text: str,
    identifier: str,
    title: str,
) -> None:
    result = _structured(_block(text))

    block = result.blocks[0]
    assert block.role is StructuralRole.SECTION_HEADING
    assert block.identifier == identifier
    assert block.title == title


def test_exact_synthetic_ambiguity_remains_unclassified() -> None:
    result = _structured(_block("2026 annual overview"))

    block = result.blocks[0]
    assert block.role is StructuralRole.UNCLASSIFIED_HEADING
    assert block.identifier is None
    assert block.title is None


def test_recognised_title_punctuation_is_preserved() -> None:
    result = _structured(_block("6 Meaning: “invented”—special?"))

    assert result.blocks[0].title == "Meaning: “invented”—special?"
    assert result.blocks[0].original_normalized_text == "6 Meaning: “invented”—special?"


def test_non_breaking_layout_whitespace_is_normalised_only_for_recognition() -> None:
    text = "Part\u00a02A\u00a0—\u00a0Invented\u00a0title"

    result = _structured(_block(text))

    block = result.blocks[0]
    assert block.role is StructuralRole.PART_HEADING
    assert block.identifier == "2A"
    assert block.title == "Invented title"
    assert block.original_normalized_text == text


@pytest.mark.parametrize(
    "text",
    [
        "Part of the application",
        "Division of responsibilities",
        "Schedule for delivery",
        "6",
        "(1) General rule",
        "(a) General rule",
        "(i) General rule",
        "6.1 Decimal heading",
        "Sections 6 and 7",
        "Part 2-1 - Preliminary",
        "The Schedule—Invented",
        "Schedule 1-2—Combined range",
        "Division 2-1—Unsupported hierarchy",
        "Subdivision AAAA—Unsupported suffix",
        "6AAAA Unsupported suffix",
        "II Interpretation",
    ],
)
def test_unsupported_or_ambiguous_heading_is_not_partially_classified(text: str) -> None:
    result = _structured(_block(text))

    block = result.blocks[0]
    assert block.role is StructuralRole.UNCLASSIFIED_HEADING
    assert block.identifier is None
    assert block.title is None
    assert block.parent_heading_ordinal is None
    assert block.active_container_heading_ordinal is None
    assert result.diagnostics[0].code is LegislationStructureDiagnosticCode.UNCLASSIFIED_HEADING


@pytest.mark.parametrize(
    ("kind", "tag", "text"),
    [
        ("paragraph", "p", "Part 2—Invented"),
        ("paragraph", "p", "6 Invented title"),
        ("list_item", "li", "Division 1—Invented"),
        ("table_cell", "td", "6A Invented title"),
        ("definition_description", "dd", "Schedule 1—Invented"),
        ("blockquote", "blockquote", "Chapter 1—Invented"),
        ("heading", "H1", "6 Invented title"),
    ],
)
def test_non_heading_candidate_text_remains_content(
    kind: EpubBlockKind,
    tag: str,
    text: str,
) -> None:
    result = _structured(_block(text, kind=kind, tag=tag))

    assert result.blocks[0].role is StructuralRole.CONTENT
    assert result.diagnostics == ()


def test_class_names_and_epub_type_do_not_create_heading_semantics() -> None:
    result = _structured(
        _block(
            "Invented prose.",
            kind="paragraph",
            tag="p",
            class_names=("Part", "section-heading"),
            epub_type="chapter",
        )
    )

    assert result.blocks[0].role is StructuralRole.CONTENT


def test_unclassified_heading_does_not_mutate_active_state() -> None:
    result = _structured(
        _block("Part 1—Invented", ordinal=0),
        _block("Part of the application", ordinal=1),
        _block("Invented body.", ordinal=2, kind="paragraph", tag="p"),
    )

    assert [block.role for block in result.blocks] == [
        StructuralRole.PART_HEADING,
        StructuralRole.UNCLASSIFIED_HEADING,
        StructuralRole.CONTENT,
    ]
    assert result.blocks[1].active_container_heading_ordinal == 0
    assert result.blocks[2].active_container_heading_ordinal == 0


def test_exact_synthetic_ambiguity_does_not_replace_active_section() -> None:
    result = _structured(
        _block("2026 Application provision", ordinal=0),
        _block("2026 annual overview", ordinal=1),
        _block("Invented body.", ordinal=2, kind="paragraph", tag="p"),
    )

    assert result.blocks[0].role is StructuralRole.SECTION_HEADING
    assert result.blocks[1].role is StructuralRole.UNCLASSIFIED_HEADING
    assert result.blocks[1].active_container_heading_ordinal == 0
    assert result.blocks[2].active_container_heading_ordinal == 0


def test_exact_synthetic_ambiguity_does_not_replace_active_schedule_clause() -> None:
    result = _structured(
        _block("Schedule 1—Invented", ordinal=0),
        _block("1500 Example", ordinal=1),
        _block("2026 annual overview", ordinal=2),
        _block("Invented body.", ordinal=3, kind="paragraph", tag="p"),
    )

    assert result.blocks[1].role is StructuralRole.SCHEDULE_CLAUSE_HEADING
    assert result.blocks[2].role is StructuralRole.UNCLASSIFIED_HEADING
    assert result.blocks[2].active_container_heading_ordinal == 1
    assert result.blocks[3].active_container_heading_ordinal == 1


def test_main_body_hierarchy_assigns_parents_and_deepest_content_container() -> None:
    result = _structured(
        _block("Chapter 1—Invented", ordinal=0),
        _block("Part 1—Invented", ordinal=1),
        _block("Division 1—Invented", ordinal=2),
        _block("Subdivision A—Invented", ordinal=3),
        _block("6 Invented section", ordinal=4),
        _block("Invented body.", ordinal=5, kind="paragraph", tag="p"),
    )

    assert [block.parent_heading_ordinal for block in result.blocks[:5]] == [
        None,
        0,
        1,
        2,
        3,
    ]
    assert [block.active_container_heading_ordinal for block in result.blocks[:5]] == [
        0,
        1,
        2,
        3,
        4,
    ]
    assert result.blocks[5].active_container_heading_ordinal == 4


@pytest.mark.parametrize(
    ("headings", "expected_parent"),
    [
        (("Chapter 1—Invented", "Division 1—Invented"), 0),
        (("Part 1—Invented", "Division 1—Invented"), 0),
        (("Chapter 1—Invented", "Subdivision A—Invented"), 0),
        (("Part 1—Invented", "Subdivision A—Invented"), 0),
        (("Division 1—Invented", "Subdivision A—Invented"), 0),
        (("Chapter 1—Invented", "6 Invented section"), 0),
        (("Part 1—Invented", "6 Invented section"), 0),
        (("Division 1—Invented", "6 Invented section"), 0),
        (("Subdivision A—Invented", "6 Invented section"), 0),
    ],
)
def test_main_body_parent_fallbacks_use_nearest_active_container(
    headings: tuple[str, str],
    expected_parent: int,
) -> None:
    result = _structured(*(_block(text, ordinal=index) for index, text in enumerate(headings)))

    assert result.blocks[1].parent_heading_ordinal == expected_parent


def test_body_without_a_container_remains_uncontained() -> None:
    result = _structured(_block("Invented body.", kind="paragraph", tag="p"))

    assert result.blocks[0].active_container_heading_ordinal is None


@pytest.mark.parametrize(
    ("blocks", "expected_parent"),
    [
        (
            (
                "Chapter 1—Old",
                "Part 1—Old",
                "Division 1—Old",
                "Subdivision A—Old",
                "Chapter 2—New",
                "7 New section",
            ),
            4,
        ),
        (("Part 1—Old", "Division 1—Old", "Part 2—New", "7 New section"), 2),
        (("Division 1—Old", "Subdivision A—Old", "Division 2—New", "7 New section"), 2),
        (("Subdivision A—Old", "6 Old section", "Subdivision B—New", "Body"), 2),
    ],
)
def test_new_hierarchy_headings_clear_only_their_lower_state(
    blocks: tuple[str, ...],
    expected_parent: int,
) -> None:
    source_blocks = tuple(
        _block(
            text,
            ordinal=index,
            kind="paragraph" if text == "Body" else "heading",
            tag="p" if text == "Body" else "h2",
        )
        for index, text in enumerate(blocks)
    )

    result = _structured(*source_blocks)

    if result.blocks[-1].role is StructuralRole.CONTENT:
        assert result.blocks[-1].active_container_heading_ordinal == expected_parent
    else:
        assert result.blocks[-1].parent_heading_ordinal == expected_parent
        assert result.blocks[-1].active_container_heading_ordinal == len(result.blocks) - 1


def test_new_section_replaces_only_active_section() -> None:
    result = _structured(
        _block("Part 1—Invented", ordinal=0),
        _block("6 First section", ordinal=1),
        _block("7 Second section", ordinal=2),
        _block("Invented body.", ordinal=3, kind="paragraph", tag="p"),
    )

    assert result.blocks[1].parent_heading_ordinal == 0
    assert result.blocks[2].parent_heading_ordinal == 0
    assert result.blocks[3].active_container_heading_ordinal == 2


@pytest.mark.parametrize(
    "replacement_heading",
    [
        "Chapter 2—Replacement",
        "Part 2—Replacement",
        "Division 2—Replacement",
    ],
)
def test_new_main_heading_clears_a_previously_active_section(
    replacement_heading: str,
) -> None:
    result = _structured(
        _block("Chapter 1—Invented", ordinal=0),
        _block("Part 1—Invented", ordinal=1),
        _block("Division 1—Invented", ordinal=2),
        _block("Subdivision A—Invented", ordinal=3),
        _block("6 Active section", ordinal=4),
        _block(replacement_heading, ordinal=5),
        _block("Invented body.", ordinal=6, kind="paragraph", tag="p"),
    )

    assert result.blocks[6].active_container_heading_ordinal == 5


def test_hierarchy_continues_deterministically_across_spine_documents() -> None:
    source = _document(
        (_block("Part 1—Invented", ordinal=0),),
        (
            _block("6 Invented section", ordinal=0),
            _block("Invented body.", ordinal=1, kind="paragraph", tag="p"),
        ),
    )

    result = structure_legislation(source)

    assert result.blocks[1].parent_heading_ordinal == 0
    assert result.blocks[2].active_container_heading_ordinal == 1


def test_schedule_resets_main_body_and_owns_following_content() -> None:
    result = _structured(
        _block("Chapter 1—Invented", ordinal=0),
        _block("6 Invented section", ordinal=1),
        _block("Schedule 1—Invented schedule", ordinal=2),
        _block("Invented schedule body.", ordinal=3, kind="paragraph", tag="p"),
    )

    assert result.blocks[2].role is StructuralRole.SCHEDULE_HEADING
    assert result.blocks[2].parent_heading_ordinal is None
    assert result.blocks[3].active_container_heading_ordinal == 2


def test_schedule_hierarchy_and_clause_roles_are_distinct_from_main_body() -> None:
    result = _structured(
        _block("Schedule 1—Invented", ordinal=0),
        _block("Part 1—Invented", ordinal=1),
        _block("Division 1—Invented", ordinal=2),
        _block("Subdivision A—Invented", ordinal=3),
        _block("6A Invented clause", ordinal=4),
        _block("Invented clause body.", ordinal=5, kind="paragraph", tag="p"),
    )

    assert [block.role for block in result.blocks[:5]] == [
        StructuralRole.SCHEDULE_HEADING,
        StructuralRole.SCHEDULE_PART_HEADING,
        StructuralRole.SCHEDULE_DIVISION_HEADING,
        StructuralRole.SCHEDULE_SUBDIVISION_HEADING,
        StructuralRole.SCHEDULE_CLAUSE_HEADING,
    ]
    assert [block.parent_heading_ordinal for block in result.blocks[:5]] == [
        None,
        0,
        1,
        2,
        3,
    ]
    assert result.blocks[4].role is not StructuralRole.SECTION_HEADING
    assert result.blocks[5].active_container_heading_ordinal == 4


@pytest.mark.parametrize(
    ("text", "identifier", "title"),
    [
        ("1500 Example", "1500", "Example"),
        ("2026 Application provision", "2026", "Application provision"),
    ],
)
def test_four_digit_provisions_inside_schedule_are_schedule_clauses(
    text: str,
    identifier: str,
    title: str,
) -> None:
    result = _structured(
        _block("Schedule 1—Invented", ordinal=0),
        _block(text, ordinal=1),
    )

    clause = result.blocks[1]
    assert clause.role != StructuralRole.SECTION_HEADING
    assert clause.role is StructuralRole.SCHEDULE_CLAUSE_HEADING
    assert clause.identifier == identifier
    assert clause.title == title
    assert clause.parent_heading_ordinal == 0


@pytest.mark.parametrize(
    ("headings", "expected_parent"),
    [
        (("Schedule 1—Invented", "Division 1—Invented"), 0),
        (("Schedule 1—Invented", "Subdivision A—Invented"), 0),
        (("Schedule 1—Invented", "6 Invented clause"), 0),
        (("Schedule 1—Invented", "Part 1—Invented", "6 Invented clause"), 1),
        (("Schedule 1—Invented", "Division 1—Invented", "6 Invented clause"), 1),
        (("Schedule 1—Invented", "Subdivision A—Invented", "6 Invented clause"), 1),
    ],
)
def test_schedule_parent_fallbacks_stay_within_the_active_schedule(
    headings: tuple[str, ...],
    expected_parent: int,
) -> None:
    result = _structured(*(_block(text, ordinal=index) for index, text in enumerate(headings)))

    assert result.blocks[-1].parent_heading_ordinal == expected_parent


def test_new_schedule_clears_lower_schedule_state_and_allows_duplicate_clause_numbers() -> None:
    result = _structured(
        _block("Schedule 1—First", ordinal=0),
        _block("Part 1—First", ordinal=1),
        _block("6 Invented clause", ordinal=2),
        _block("Schedule 2—Second", ordinal=3),
        _block("6 Invented clause", ordinal=4),
    )

    assert result.blocks[2].role is StructuralRole.SCHEDULE_CLAUSE_HEADING
    assert result.blocks[4].role is StructuralRole.SCHEDULE_CLAUSE_HEADING
    assert result.blocks[4].identifier == "6"
    assert result.blocks[4].parent_heading_ordinal == 3


@pytest.mark.parametrize(
    "replacement_heading",
    [
        "Part 2—Replacement",
        "Division 2—Replacement",
        "Subdivision B—Replacement",
    ],
)
def test_new_schedule_heading_clears_a_previously_active_clause(
    replacement_heading: str,
) -> None:
    result = _structured(
        _block("Schedule 1—Invented", ordinal=0),
        _block("Part 1—Invented", ordinal=1),
        _block("Division 1—Invented", ordinal=2),
        _block("Subdivision A—Invented", ordinal=3),
        _block("6 Active clause", ordinal=4),
        _block(replacement_heading, ordinal=5),
        _block("Invented body.", ordinal=6, kind="paragraph", tag="p"),
    )

    assert result.blocks[6].active_container_heading_ordinal == 5


def test_chapter_after_schedule_returns_to_main_body_hierarchy() -> None:
    result = _structured(
        _block("Schedule 1—Invented", ordinal=0),
        _block("6 Invented clause", ordinal=1),
        _block("Chapter 2—Invented", ordinal=2),
        _block("7 Invented section", ordinal=3),
    )

    assert result.blocks[2].role is StructuralRole.CHAPTER_HEADING
    assert result.blocks[3].role is StructuralRole.SECTION_HEADING
    assert result.blocks[3].parent_heading_ordinal == 2


def test_endnotes_is_an_exact_boundary_that_clears_all_hierarchy() -> None:
    result = _structured(
        _block("Schedule 1—Invented", ordinal=0),
        _block("6 Invented clause", ordinal=1),
        _block("Endnotes", ordinal=2),
        _block("Chapter 9—History", ordinal=3),
        _block("7 Amendment history", ordinal=4),
        _block("Invented endnote body.", ordinal=5, kind="paragraph", tag="p"),
    )

    assert result.blocks[2].role is StructuralRole.ENDNOTES_HEADING
    assert result.blocks[2].parent_heading_ordinal is None
    assert result.blocks[2].active_container_heading_ordinal == 2
    assert result.blocks[3].role is StructuralRole.UNCLASSIFIED_HEADING
    assert result.blocks[4].role is StructuralRole.UNCLASSIFIED_HEADING
    assert result.blocks[3].active_container_heading_ordinal is None
    assert result.blocks[4].active_container_heading_ordinal is None
    assert result.blocks[5].role is StructuralRole.CONTENT
    assert result.blocks[5].active_container_heading_ordinal is None


def test_endnotes_clears_a_fully_populated_main_body_hierarchy() -> None:
    result = _structured(
        _block("Chapter 1—Invented", ordinal=0),
        _block("Part 1—Invented", ordinal=1),
        _block("Division 1—Invented", ordinal=2),
        _block("Subdivision A—Invented", ordinal=3),
        _block("6 Active section", ordinal=4),
        _block("Endnotes", ordinal=5),
        _block("Invented endnote body.", ordinal=6, kind="paragraph", tag="p"),
    )

    assert result.blocks[6].active_container_heading_ordinal is None


@pytest.mark.parametrize("text", ["endnotes", "Endnotes:", "End notes", "The Endnotes"])
def test_only_exact_endnotes_text_creates_the_boundary(text: str) -> None:
    result = _structured(_block(text))

    assert result.blocks[0].role is StructuralRole.UNCLASSIFIED_HEADING


def test_repealed_is_only_a_section_title_not_a_semantic_role() -> None:
    result = _structured(_block("6 Repealed"))

    assert result.blocks[0].role is StructuralRole.SECTION_HEADING
    assert result.blocks[0].identifier == "6"
    assert result.blocks[0].title == "Repealed"


def test_unclassified_heading_diagnostic_is_bounded_and_source_linked() -> None:
    result = _structured(_block("Invented heading", locator="EPUB/body.xhtml#unknown"))

    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.global_block_ordinal == 0
    assert diagnostic.source_locator == "EPUB/body.xhtml#unknown"
    assert diagnostic.code is LegislationStructureDiagnosticCode.UNCLASSIFIED_HEADING
    assert "Invented heading" not in diagnostic.model_dump_json()


def test_repeated_execution_has_identical_model_json() -> None:
    source = _document(
        (
            _block("Part 1—Invented", ordinal=0),
            _block("6 Invented section", ordinal=1),
            _block("Invented body.", ordinal=2, kind="paragraph", tag="p"),
        ),
    )

    first = structure_legislation(source)
    second = structure_legislation(source)

    assert first.model_dump_json() == second.model_dump_json()


def test_input_models_are_not_mutated() -> None:
    source = _document(
        (
            _block("Part 1—Invented", ordinal=0),
            _block("6 Invented section", ordinal=1),
        ),
    )
    before = source.model_dump_json()

    structure_legislation(source)

    assert source.model_dump_json() == before


def test_output_models_are_frozen_and_forbid_extra_fields() -> None:
    result = _structured(_block("6 Invented section"))

    with pytest.raises(ValidationError):
        result.package_title = "Changed"
    with pytest.raises(ValidationError):
        type(result).model_validate({**result.model_dump(), "arbitrary": "metadata"})
    with pytest.raises(ValidationError):
        type(result.blocks[0]).model_validate(
            {**result.blocks[0].model_dump(), "arbitrary": "metadata"}
        )


def test_structured_block_model_is_frozen() -> None:
    block = _structured(_block("6 Invented section")).blocks[0]

    with pytest.raises(ValidationError):
        block.title = "Changed"


def test_structural_role_enum_contains_only_authorised_roles() -> None:
    assert {role.value for role in StructuralRole} == {
        "content",
        "unclassified_heading",
        "chapter_heading",
        "part_heading",
        "division_heading",
        "subdivision_heading",
        "section_heading",
        "schedule_heading",
        "schedule_part_heading",
        "schedule_division_heading",
        "schedule_subdivision_heading",
        "schedule_clause_heading",
        "endnotes_heading",
    }


def test_public_api_rejects_non_parsed_input_with_typed_error() -> None:
    with pytest.raises(LegislationStructureValidationError):
        structure_legislation(cast(ParsedEpubDocument, {"blocks": []}))


def test_accidental_processing_error_is_translated_at_public_boundary() -> None:
    malformed = ParsedEpubDocument.model_construct(
        artifact_sha256="a" * 64,
        package_identifier=None,
        package_title=None,
        language=None,
        spine_documents=cast(tuple[EpubSpineDocument, ...], None),
    )

    with pytest.raises(LegislationStructureValidationError) as caught:
        structure_legislation(malformed)

    assert isinstance(caught.value.__cause__, TypeError)


def test_validation_error_belongs_to_public_error_hierarchy() -> None:
    assert issubclass(LegislationStructureValidationError, LegislationStructureError)


def test_public_models_are_available_from_package_interface() -> None:
    assert StructuredLegislationDocument.__name__ == "StructuredLegislationDocument"
    assert StructuredLegislationBlock.__name__ == "StructuredLegislationBlock"
