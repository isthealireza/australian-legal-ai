"""Extraction records its tool, normalises predictably, and never verifies.

`pdftotext` is never actually invoked: the command runner is injected, so these
tests are deterministic on any machine and shell out to nothing.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from scripts.wa_ingest.extraction import (
    POPPLER,
    XPDF,
    ExtractionError,
    ExtractionTool,
    SectionDraft,
    build_sections_file,
    detect_tool,
    extract_page_range,
    normalise_extracted_text,
    require_tool,
    section_text_digest,
    verify_staged_digest,
)

_POPPLER_BANNER = "pdftotext version 24.02.0\nCopyright 2005-2024 The Poppler Developers\n"
_XPDF_BANNER = "pdftotext version 4.06 [www.xpdfreader.com]\nCopyright 1996-2025 Glyph & Cog, LLC\n"

_TOOL = ExtractionTool(implementation=POPPLER, version="24.02.0")


def runner_returning(output: str) -> Callable[[Sequence[str]], str]:
    def _run(command: Sequence[str]) -> str:
        return output

    return _run


# ---------------------------------------------------------------------------
# Tool identity — the reason a sections file is reproducible at all
# ---------------------------------------------------------------------------


def test_poppler_is_identified() -> None:
    tool = detect_tool(runner_returning(_POPPLER_BANNER))
    assert tool == ExtractionTool(implementation=POPPLER, version="24.02.0")


def test_xpdf_is_identified_and_not_mistaken_for_poppler() -> None:
    """ADR 0014 used poppler. Xpdf lays text out differently, so digests differ."""

    tool = detect_tool(runner_returning(_XPDF_BANNER))
    assert tool.implementation == XPDF
    assert tool.version == "4.06"


def test_an_unrecognised_implementation_is_refused_not_guessed() -> None:
    with pytest.raises(ExtractionError, match="could not be identified"):
        detect_tool(runner_returning("pdftotext version 9.9.9\nCopyright Someone Else\n"))


def test_an_unparseable_banner_is_refused() -> None:
    with pytest.raises(ExtractionError, match="unrecognised"):
        detect_tool(runner_returning("not a version banner at all"))


def test_a_missing_pdftotext_is_refused() -> None:
    def _missing(command: Sequence[str]) -> str:
        raise FileNotFoundError(command[0])

    with pytest.raises(ExtractionError, match="not installed"):
        detect_tool(_missing)


# ---------------------------------------------------------------------------
# Normalisation — ADR 0014 §6, and nothing beyond it
# ---------------------------------------------------------------------------


def test_line_endings_become_lf() -> None:
    assert normalise_extracted_text("a\r\nb\rc") == "a\nb\nc"


def test_trailing_whitespace_is_stripped_per_line() -> None:
    assert normalise_extracted_text("a   \nb\t\n") == "a\nb"


def test_blank_line_runs_collapse_to_one() -> None:
    assert normalise_extracted_text("a\n\n\n\n\nb") == "a\n\nb"


def test_a_single_blank_line_is_preserved() -> None:
    assert normalise_extracted_text("a\n\nb") == "a\n\nb"


def test_normalisation_is_idempotent() -> None:
    once = normalise_extracted_text("  a  \r\n\n\n b \n\n")
    assert normalise_extracted_text(once) == once


def test_normalisation_changes_no_characters_inside_a_line() -> None:
    """No spelling, punctuation or content correction. The text stays the source's."""

    line = "s 55(2)(a) — a vehicle's “owner” must, within 48 hours..."
    assert normalise_extracted_text(line) == line


def test_oversized_extraction_is_refused() -> None:
    with pytest.raises(ExtractionError, match="exceeds"):
        normalise_extracted_text("x" * 2_000_001)


# ---------------------------------------------------------------------------
# Page ranges
# ---------------------------------------------------------------------------


def test_a_page_range_is_extracted_and_normalised(tmp_path: Path) -> None:
    pdf = tmp_path / "staged.pdf"
    pdf.write_bytes(b"%PDF-1.7")
    text = extract_page_range(
        pdf_path=pdf,
        first_page=3,
        last_page=4,
        runner=runner_returning("line one   \r\n\n\n\nline two\n"),
    )
    assert text == "line one\n\nline two"


@pytest.mark.parametrize(("first", "last"), [(0, 3), (-1, 2), (5, 4)])
def test_an_invalid_page_range_is_refused(tmp_path: Path, first: int, last: int) -> None:
    pdf = tmp_path / "staged.pdf"
    pdf.write_bytes(b"%PDF-1.7")
    with pytest.raises(ExtractionError, match="invalid page range"):
        extract_page_range(
            pdf_path=pdf,
            first_page=first,
            last_page=last,
            runner=runner_returning(""),
        )


def test_extracting_from_a_missing_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ExtractionError, match="no such staged file"):
        extract_page_range(
            pdf_path=tmp_path / "absent.pdf",
            first_page=1,
            last_page=1,
            runner=runner_returning(""),
        )


# ---------------------------------------------------------------------------
# The sections file
# ---------------------------------------------------------------------------


def draft(identifier: str = "s 55", text: str = "Body text.") -> SectionDraft:
    return SectionDraft(identifier=identifier, heading="Heading", text=text)


def build(
    *,
    source_id: str = "wa_legislation:synthetic_act_2012:consolidated:01-j0-00",
    source_document_sha256: str = "a" * 64,
    tool: ExtractionTool = _TOOL,
    drafts: Sequence[SectionDraft] | None = None,
) -> dict[str, Any]:
    return build_sections_file(
        source_id=source_id,
        source_document_sha256=source_document_sha256,
        tool=tool,
        drafts=[draft()] if drafts is None else drafts,
    )


def test_every_section_ships_unverified() -> None:
    payload = build(drafts=[draft("s 55"), draft("s 56")])
    assert [record["verified"] for record in payload["sections"]] == [False, False]


def test_there_is_no_parameter_that_could_set_verified_true() -> None:
    """Gate G2 is a human act. The builder has no way to express it."""

    with pytest.raises(TypeError):
        build_sections_file(  # type: ignore[call-arg]
            source_id="x",
            source_document_sha256="a" * 64,
            tool=_TOOL,
            drafts=[draft()],
            verified=True,
        )


def test_the_extraction_tool_is_recorded() -> None:
    assert build()["extraction"]["tool"] == {
        "implementation": POPPLER,
        "version": "24.02.0",
    }


def test_the_parent_binding_is_recorded() -> None:
    payload = build()
    assert payload["source_id"] == "wa_legislation:synthetic_act_2012:consolidated:01-j0-00"
    assert payload["source_document_sha256"] == "a" * 64


def test_digests_use_the_adr_0014_convention() -> None:
    text = "Body text."
    payload = build(drafts=[draft(text=text)])
    assert payload["sections"][0]["text_sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert section_text_digest(text) == payload["sections"][0]["text_sha256"]


def test_duplicate_identifiers_are_refused_at_build_time() -> None:
    with pytest.raises(ExtractionError, match="duplicate section identifier"):
        build(drafts=[draft("s 55"), draft("S  55")])


def test_an_empty_sections_file_is_refused() -> None:
    with pytest.raises(ExtractionError, match="no sections"):
        build(drafts=[])


def test_a_section_with_no_text_is_refused() -> None:
    with pytest.raises(ExtractionError, match="extracted no text"):
        SectionDraft(identifier="s 55", heading=None, text="   \n  ")


def test_a_blank_identifier_is_refused() -> None:
    with pytest.raises(ExtractionError, match="must not be blank"):
        SectionDraft(identifier="  ", heading=None, text="Body.")


# ---------------------------------------------------------------------------
# Staged digest re-check
# ---------------------------------------------------------------------------


def test_a_staged_file_that_changed_since_staging_is_refused(tmp_path: Path) -> None:
    pdf = tmp_path / "staged.pdf"
    pdf.write_bytes(b"original")
    original = hashlib.sha256(b"original").hexdigest()
    verify_staged_digest(pdf, original)

    pdf.write_bytes(b"tampered")
    with pytest.raises(ExtractionError, match="digest changed"):
        verify_staged_digest(pdf, original)


# ---------------------------------------------------------------------------
# The expected-implementation guard
# ---------------------------------------------------------------------------


def test_the_expected_implementation_passes() -> None:
    require_tool(ExtractionTool(implementation=POPPLER, version="24.02.0"))


def test_a_different_implementation_is_refused_by_default() -> None:
    """Xpdf is what this workstation has. It must not be used by accident."""

    with pytest.raises(ExtractionError, match="expected poppler-utils"):
        require_tool(ExtractionTool(implementation=XPDF, version="4.06"))


def test_a_different_implementation_can_be_accepted_deliberately() -> None:
    require_tool(ExtractionTool(implementation=XPDF, version="4.06"), expected=XPDF)
