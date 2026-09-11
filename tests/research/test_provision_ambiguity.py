"""Provision resolution refuses ambiguity instead of picking by list order."""

from __future__ import annotations

import pytest

from legal_ai.research.models import RecordedProvision
from legal_ai.research.types import ResearchRefusalCode
from legal_ai.research.validation import validate_recorded_source
from tests.research.conftest import query, recorded_source

_HEADING = "Synthetic heading"


def _provision(identifier: str, pinpoint: str) -> RecordedProvision:
    return RecordedProvision(identifier=identifier, pinpoint=pinpoint, heading=_HEADING)


def test_single_match_still_validates() -> None:
    result = validate_recorded_source(query(), recorded_source())
    assert not isinstance(result, ResearchRefusalCode)


def test_duplicate_identifier_refuses_rather_than_taking_the_first() -> None:
    source = recorded_source(
        provisions=(
            _provision("s 55", "section 55"),
            _provision("s 55", "section 55"),
        )
    )
    result = validate_recorded_source(query(), source)
    assert result is ResearchRefusalCode.PROVISION_AMBIGUOUS


def test_duplicate_after_normalisation_refuses() -> None:
    """`normalize_for_match` collapses whitespace and case, so these collide."""

    source = recorded_source(
        provisions=(
            _provision("s 55", "section 55"),
            _provision("S  55", "SECTION  55"),
        )
    )
    result = validate_recorded_source(query(), source)
    assert result is ResearchRefusalCode.PROVISION_AMBIGUOUS


def test_one_provisions_pinpoint_colliding_with_anothers_identifier_refuses() -> None:
    """The subtle case: no record is duplicated, but the request is ambiguous.

    Neither provision is a duplicate of the other. The request `section 55`
    nonetheless matches the first by its **pinpoint** and the second by its
    **identifier**, so list order alone would decide which law is cited.
    """

    source = recorded_source(
        provisions=(
            _provision("s 55", "section 55"),
            _provision("section 55", "section 55A"),
        )
    )
    result = validate_recorded_source(query(provision_identifier="section 55"), source)
    assert result is ResearchRefusalCode.PROVISION_AMBIGUOUS


def test_a_cross_field_collision_the_request_does_not_touch_still_validates() -> None:
    """Ambiguity is per request, not a whole-source property.

    The same two provisions are present, but `s 55` matches only the first, so
    the request is unambiguous and must still be answered.
    """

    source = recorded_source(
        provisions=(
            _provision("s 55", "section 55"),
            _provision("section 55", "section 55A"),
        )
    )
    result = validate_recorded_source(query(), source)
    assert not isinstance(result, ResearchRefusalCode)
    assert result.provision_identifier == "s 55"


def test_ambiguity_is_refused_even_when_the_first_match_would_be_correct() -> None:
    """Order independence: the duplicate is second, and it still refuses."""

    source = recorded_source(
        provisions=(
            _provision("s 55", "section 55"),
            _provision("s 56", "section 56"),
            _provision("s 55", "section 55"),
        )
    )
    result = validate_recorded_source(query(), source)
    assert result is ResearchRefusalCode.PROVISION_AMBIGUOUS


def test_reordering_distinct_provisions_does_not_change_the_result() -> None:
    forward = recorded_source(
        provisions=(_provision("s 55", "section 55"), _provision("s 56", "section 56"))
    )
    reversed_ = recorded_source(
        provisions=(_provision("s 56", "section 56"), _provision("s 55", "section 55"))
    )
    left = validate_recorded_source(query(), forward)
    right = validate_recorded_source(query(), reversed_)
    assert not isinstance(left, ResearchRefusalCode)
    assert not isinstance(right, ResearchRefusalCode)
    assert left.provision_identifier == right.provision_identifier == "s 55"


def test_absent_provision_still_refuses_citation_not_found() -> None:
    """The existing code is unchanged for the not-found case."""

    result = validate_recorded_source(query(provision_identifier="s 99"), recorded_source())
    assert result is ResearchRefusalCode.CITATION_NOT_FOUND


@pytest.mark.parametrize("pinpoint", ["section 56", "section 99"])
def test_wrong_pinpoint_still_refuses_pinpoint_mismatch(pinpoint: str) -> None:
    result = validate_recorded_source(query(pinpoint=pinpoint), recorded_source())
    assert result is ResearchRefusalCode.PINPOINT_MISMATCH
