"""The section verification gate refuses everything it cannot prove."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from legal_ai.research.corpus import RecordedWaCorpus
from legal_ai.research.models import RecordedProvision, RecordedSection
from legal_ai.research.sections import (
    VerifiedSection,
    section_text_digest,
    verify_section,
)
from legal_ai.research.types import ResearchRefusalCode
from tests.research.conftest import (
    RECORDED_FIXTURE_ROOT,
    RECORDED_SHA256,
    RECORDED_SOURCE_ID,
    recorded_query,
    recorded_source,
)

_TEXT = "A synthetic provision body used only for gate tests."
_DIGEST = section_text_digest(_TEXT)


def _section(**overrides: Any) -> RecordedSection:
    fields: dict[str, Any] = {
        "identifier": "s 55",
        "heading": "Synthetic heading",
        "text": _TEXT,
        "text_sha256": _DIGEST,
        "verified": True,
    }
    fields.update(overrides)
    return RecordedSection(**fields)


def _bound_source(**overrides: Any) -> Any:
    """A synthetic source whose companion file claims the source correctly."""

    fields: dict[str, Any] = {
        "sections": (_section(),),
        "sections_source_id": "wa_legislation:synthetic_act_1974:consolidated:1-a0-00",
        "sections_source_document_sha256": recorded_source().sha256,
    }
    fields.update(overrides)
    return recorded_source(**fields)


# ---------------------------------------------------------------------------
# The happy path exists, so the refusals below mean something
# ---------------------------------------------------------------------------


def test_a_fully_verified_section_passes() -> None:
    result = verify_section(source=_bound_source(), identifier="s 55")
    assert isinstance(result, VerifiedSection)
    assert result.identifier == "s 55"
    assert result.text == _TEXT
    assert result.text_sha256 == _DIGEST


# ---------------------------------------------------------------------------
# 1. Parent-document binding
# ---------------------------------------------------------------------------


def test_unbound_companion_file_refuses() -> None:
    """A sections file that declared nothing is refused, not trusted."""

    source = _bound_source(sections_source_id=None, sections_source_document_sha256=None)
    assert verify_section(source=source, identifier="s 55") is (
        ResearchRefusalCode.SECTION_SOURCE_MISMATCH
    )


def test_companion_file_naming_another_source_refuses() -> None:
    source = _bound_source(sections_source_id="wa_legislation:other_act_1999:consolidated:1-a0-00")
    assert verify_section(source=source, identifier="s 55") is (
        ResearchRefusalCode.SECTION_SOURCE_MISMATCH
    )


def test_companion_file_naming_another_document_digest_refuses() -> None:
    """The case the loader could not previously see at all."""

    source = _bound_source(sections_source_document_sha256="0" * 64)
    assert verify_section(source=source, identifier="s 55") is (
        ResearchRefusalCode.SECTION_SOURCE_MISMATCH
    )


def test_binding_is_checked_before_anything_inside_the_file() -> None:
    """A perfect section in a mis-bound file is still refused on binding."""

    source = _bound_source(
        sections_source_id=None,
        sections_source_document_sha256=None,
        sections=(_section(identifier="s 999", verified=False, text_sha256="0" * 64),),
    )
    assert verify_section(source=source, identifier="s 999") is (
        ResearchRefusalCode.SECTION_SOURCE_MISMATCH
    )


# ---------------------------------------------------------------------------
# 2 and 3. Resolution and manifest binding
# ---------------------------------------------------------------------------


def test_no_section_record_refuses() -> None:
    assert verify_section(source=_bound_source(sections=()), identifier="s 55") is (
        ResearchRefusalCode.SECTION_TEXT_MISSING
    )


def test_duplicate_section_identifiers_refuse() -> None:
    source = _bound_source(sections=(_section(), _section()))
    assert verify_section(source=source, identifier="s 55") is (
        ResearchRefusalCode.SECTION_AMBIGUOUS
    )


def test_duplicate_after_normalisation_refuses() -> None:
    source = _bound_source(sections=(_section(), _section(identifier="S  55")))
    assert verify_section(source=source, identifier="s 55") is (
        ResearchRefusalCode.SECTION_AMBIGUOUS
    )


def test_section_the_manifest_never_declared_refuses() -> None:
    """A sections file cannot smuggle in a provision the manifest omits."""

    source = _bound_source(sections=(_section(identifier="s 999"),))
    assert verify_section(source=source, identifier="s 999") is (
        ResearchRefusalCode.SECTION_NOT_IN_MANIFEST
    )


def test_section_whose_manifest_entry_is_ambiguous_refuses() -> None:
    source = _bound_source(
        provisions=(
            RecordedProvision(identifier="s 55", pinpoint="section 55", heading="a"),
            RecordedProvision(identifier="s 55", pinpoint="section 55", heading="b"),
        )
    )
    assert verify_section(source=source, identifier="s 55") is (
        ResearchRefusalCode.SECTION_NOT_IN_MANIFEST
    )


# ---------------------------------------------------------------------------
# 4. verified must be exactly True
# ---------------------------------------------------------------------------


def test_unverified_section_refuses() -> None:
    source = _bound_source(sections=(_section(verified=False),))
    assert verify_section(source=source, identifier="s 55") is (
        ResearchRefusalCode.SECTION_NOT_VERIFIED
    )


@pytest.mark.parametrize("value", ["yes", "true", "True", 1, 0, None, [], object()])
def test_only_the_exact_boolean_true_passes_the_verified_gate(value: object) -> None:
    """Identity, not truthiness. A truthy value must not be an acceptance."""

    source = _bound_source(sections=(_section(verified=value),))
    assert verify_section(source=source, identifier="s 55") is (
        ResearchRefusalCode.SECTION_NOT_VERIFIED
    )


def test_verified_is_checked_before_the_digest() -> None:
    """An unverified section refuses on verification, not incidentally on digest."""

    source = _bound_source(sections=(_section(verified=False, text_sha256="0" * 64),))
    assert verify_section(source=source, identifier="s 55") is (
        ResearchRefusalCode.SECTION_NOT_VERIFIED
    )


# ---------------------------------------------------------------------------
# 5. Digest
# ---------------------------------------------------------------------------


def test_digest_mismatch_refuses_even_when_verified_is_true() -> None:
    """Human verification never overrides a failed digest."""

    source = _bound_source(sections=(_section(text_sha256="0" * 64),))
    assert verify_section(source=source, identifier="s 55") is (
        ResearchRefusalCode.SECTION_TEXT_HASH_MISMATCH
    )


def test_tampered_text_with_the_original_digest_refuses() -> None:
    source = _bound_source(sections=(_section(text=_TEXT + " tampered"),))
    assert verify_section(source=source, identifier="s 55") is (
        ResearchRefusalCode.SECTION_TEXT_HASH_MISMATCH
    )


# ---------------------------------------------------------------------------
# VerifiedSection cannot be forged
# ---------------------------------------------------------------------------


def test_verified_section_cannot_be_constructed_with_a_bad_digest() -> None:
    with pytest.raises(ValidationError):
        VerifiedSection(
            source_id=RECORDED_SOURCE_ID,
            identifier="s 55",
            heading=None,
            text=_TEXT,
            text_sha256="0" * 64,
        )


def test_verified_section_cannot_be_forged_by_model_validate() -> None:
    with pytest.raises(ValidationError):
        VerifiedSection.model_validate(
            {
                "source_id": RECORDED_SOURCE_ID,
                "identifier": "s 55",
                "heading": None,
                "text": _TEXT,
                "text_sha256": "0" * 64,
            }
        )


# ---------------------------------------------------------------------------
# The real fixture: the gate is closed until a human verifies the text
# ---------------------------------------------------------------------------


def test_the_recorded_fixture_is_bound_to_its_own_document() -> None:
    """The companion file does claim the right source, so binding is not the blocker."""

    source = RecordedWaCorpus(RECORDED_FIXTURE_ROOT).select(recorded_query())
    assert source is not None
    assert source.sections_source_id == RECORDED_SOURCE_ID
    assert source.sections_source_document_sha256 == RECORDED_SHA256


@pytest.mark.parametrize("identifier", ["s 55", "s 56"])
def test_recorded_sections_refuse_because_no_human_has_verified_them(identifier: str) -> None:
    """Gate G2 in ADR 0017. E0-A must not pre-empt human acceptance."""

    source = RecordedWaCorpus(RECORDED_FIXTURE_ROOT).select(recorded_query())
    assert source is not None
    assert verify_section(source=source, identifier=identifier) is (
        ResearchRefusalCode.SECTION_NOT_VERIFIED
    )


def test_model_construct_bypasses_validation_and_is_pinned_as_such() -> None:
    """`model_construct` is a documented Pydantic bypass, not a gate failure.

    It is pinned here so nobody later assumes `VerifiedSection` is unforgeable
    by every route. Real code must go through `verify_section`; re-validating a
    constructed value catches the tampering.
    """

    forged = VerifiedSection.model_construct(
        source_id=RECORDED_SOURCE_ID,
        identifier="s 55",
        heading=None,
        text="tampered",
        text_sha256="0" * 64,
    )
    assert forged.text == "tampered"

    with pytest.raises(ValidationError):
        VerifiedSection.model_validate(
            {
                "source_id": forged.source_id,
                "identifier": forged.identifier,
                "heading": forged.heading,
                "text": forged.text,
                "text_sha256": forged.text_sha256,
            }
        )


def test_model_copy_also_skips_validators() -> None:
    verified = verify_section(source=_bound_source(), identifier="s 55")
    assert isinstance(verified, VerifiedSection)

    tampered = verified.model_copy(update={"text": "tampered"})
    assert tampered.text == "tampered"

    with pytest.raises(ValidationError):
        VerifiedSection.model_validate(
            {
                "source_id": tampered.source_id,
                "identifier": tampered.identifier,
                "heading": tampered.heading,
                "text": tampered.text,
                "text_sha256": tampered.text_sha256,
            }
        )
