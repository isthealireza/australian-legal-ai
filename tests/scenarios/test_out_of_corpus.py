"""FAMILY 2 — OUT OF CORPUS.

A real Australian Act the corpus has not recorded. The expected outcome is a
typed refusal, never a near-miss answer derived from a different Act.

Grounding: none of the six manifests under ``tests/fixtures/wa_legislation/``
carries any of these titles, so no recorded source can satisfy the query. The
only value the corpus returns here is the absence of a match, which the
pipeline reports as ``RETRIEVAL_MISSING``.
"""

from __future__ import annotations

import pytest

from legal_ai.research.service import ResearchRefused
from legal_ai.research.types import ResearchRefusalCode
from tests.scenarios.conftest import new_service, wa_query

# (act_title, provision_identifier, pinpoint, why_recording_is_absent)
_SCENARIOS = (
    (
        "Work Health and Safety Act 2020",
        "s 19",
        "section 19",
        "real WA Act, not one of the six recorded manifests",
    ),
    (
        "Corporations Act 2001",
        "s 180",
        "section 180",
        "Commonwealth Act, never recorded in this corpus",
    ),
    (
        "Limitation Act 2005",
        "s 13",
        "section 13",
        "real WA Act, not recorded; s 13 is recorded only for Sale of Goods Act 1895",
    ),
    (
        "Fair Work Act 2009",
        "s 386",
        "section 386",
        "Commonwealth Act, deferred from the MVP corpus (MVP roadmap section 4)",
    ),
)


@pytest.mark.parametrize(
    ("act_title", "identifier", "pinpoint", "why"),
    _SCENARIOS,
    ids=[
        title.replace(" ", "-").replace("(", "").replace(")", "") for title, _, _, _ in _SCENARIOS
    ],
)
def test_out_of_corpus_scenario_refuses(
    act_title: str, identifier: str, pinpoint: str, why: str
) -> None:
    service = new_service()

    result = service.research(
        wa_query(act_title=act_title, provision_identifier=identifier, pinpoint=pinpoint)
    )

    # REFUSAL: the corpus has no recorded source for this Act title. A
    # different Act (even a neighbouring recorded one) must never be
    # substituted. Grounding note: no manifest under tests/fixtures/
    # wa_legislation/ declares this title — {why}.
    assert isinstance(result, ResearchRefused)
    assert result.code is ResearchRefusalCode.RETRIEVAL_MISSING
    assert not hasattr(result, "packet")
