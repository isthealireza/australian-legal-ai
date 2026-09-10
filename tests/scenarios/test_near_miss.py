"""FAMILY 8 — NEAR MISS.

The most important family. A question that comes close to a recorded citation —
a section number that exists in one recorded Act but is asked about another
recorded Act, a repealed/renumbered or adjacent-but-unrecorded provision, or a
different Act whose text is given effect by a recorded section — must be
refused, never answered with a plausible neighbouring provision. Silent
substitution is the failure mode that ends this project.

Grounding: the pipeline matches a citation only against the exact recorded
``identifier``/``pinpoint`` forms in the six manifests under
``tests/fixtures/wa_legislation/``. Every number below is either recorded
somewhere in the corpus (and therefore the *trap* is real) or is provably
absent from the named Act's recorded provisions.
"""

from __future__ import annotations

import pytest

from legal_ai.research.service import ResearchRefused
from legal_ai.research.types import ResearchRefusalCode
from tests.scenarios.conftest import new_service, wa_query

# (act_title, provision_identifier, pinpoint, expected, why)
_NEAR_MISSES = (
    # A section number recorded in one Act, asked about another recorded Act.
    (
        "Fair Trading Act 2010",
        "s 13",
        "section 13",
        ResearchRefusalCode.CITATION_NOT_FOUND,
        "s 13 is recorded for Sale of Goods Act 1895 ('Sale by description'), not for the "
        "Fair Trading Act; answering would substitute the SoG provision",
    ),
    (
        "Sale of Goods Act 1895",
        "s 18",
        "section 18",
        ResearchRefusalCode.CITATION_NOT_FOUND,
        "s 18 is recorded for Fair Trading Act 2010 and the Security of Payment Act, not for "
        "the Sale of Goods Act; answering would substitute a foreign provision",
    ),
    (
        "Building and Construction Industry (Security of Payment) Act 2021",
        "s 15",
        "section 15",
        ResearchRefusalCode.CITATION_NOT_FOUND,
        "s 15 is recorded for Sale of Goods and Motor Vehicle Dealers, not for the Security "
        "of Payment Act",
    ),
    # Motor Vehicle Dealers Act: s 3, s 4, s 6 and s 7 do not exist in the
    # recorded provisions (s 5, s 5A, s 15 and s 30 are the recorded pinpoints).
    (
        "Motor Vehicle Dealers Act 1973",
        "s 3",
        "section 3",
        ResearchRefusalCode.CITATION_NOT_FOUND,
        "adjacent to recorded s 5 but not itself recorded",
    ),
    (
        "Motor Vehicle Dealers Act 1973",
        "s 4",
        "section 4",
        ResearchRefusalCode.CITATION_NOT_FOUND,
        "adjacent to recorded s 5 but not itself recorded",
    ),
    (
        "Motor Vehicle Dealers Act 1973",
        "s 6",
        "section 6",
        ResearchRefusalCode.CITATION_NOT_FOUND,
        "adjacent to recorded s 5/s 5A but not itself recorded",
    ),
    (
        "Motor Vehicle Dealers Act 1973",
        "s 7",
        "section 7",
        ResearchRefusalCode.CITATION_NOT_FOUND,
        "adjacent to recorded s 5/s 5A but not itself recorded",
    ),
    # Owner-Drivers Act: s 5 was deliberately not recorded (s 4, s 6, s 7 are).
    (
        "Owner-Drivers (Contracts and Disputes) Act 2007",
        "s 5",
        "section 5",
        ResearchRefusalCode.CITATION_NOT_FOUND,
        "intentionally left unrecorded between recorded s 4 and s 6; must not be answered "
        "from either neighbour",
    ),
    # Road Traffic Act README exclusion: s 54 and s 57 are explicitly excluded.
    (
        "Road Traffic Act 1974",
        "s 54",
        "section 54",
        ResearchRefusalCode.CITATION_NOT_FOUND,
        "adjacent to recorded s 55 but excluded by the fixture README (bodily-harm duty)",
    ),
    (
        "Road Traffic Act 1974",
        "s 57",
        "section 57",
        ResearchRefusalCode.CITATION_NOT_FOUND,
        "adjacent to recorded s 56 but excluded by the fixture README (owner-identification duty)",
    ),
    # Renumbered/repealed-style gaps inside a recorded Act's provision set.
    (
        "Building and Construction Industry (Security of Payment) Act 2021",
        "s 21",
        "section 21",
        ResearchRefusalCode.CITATION_NOT_FOUND,
        "between recorded s 18 and s 22 but not recorded; a renumbered or repealed provision "
        "is never guessed",
    ),
    (
        "Building and Construction Industry (Security of Payment) Act 2021",
        "s 23",
        "section 23",
        ResearchRefusalCode.CITATION_NOT_FOUND,
        "between recorded s 22 and s 25 but not recorded",
    ),
    # A different Act whose text is given effect by a recorded section: the ACL
    # (Schedule 2 to the Competition and Consumer Act 2010 (Cth)) is applied in
    # WA by Fair Trading Act s 19, but the Cth Act itself is not recorded.
    (
        "Competition and Consumer Act 2010",
        "s 23",
        "section 23",
        ResearchRefusalCode.RETRIEVAL_MISSING,
        "no recorded source carries the Commonwealth title; answering via Fair Trading Act "
        "s 19 would be silent substitution of a different Act",
    ),
    # Pinpoint substitution: the right Act and section, wrong recorded pinpoint.
    (
        "Sale of Goods Act 1895",
        "s 13",
        "section 14",
        ResearchRefusalCode.PINPOINT_MISMATCH,
        "s 13 exists but the requested pinpoint resolves to s 14; the neighbouring "
        "provision is never substituted",
    ),
    # A plausible-sounding alias that is not a recorded identifier.
    (
        "Road Traffic Act 1974",
        "s 55A",
        "section 55A",
        ResearchRefusalCode.CITATION_NOT_FOUND,
        "an alphanumeric variant of recorded s 55 that is not itself recorded",
    ),
)


@pytest.mark.parametrize(
    ("act_title", "identifier", "pinpoint", "expected", "why"),
    _NEAR_MISSES,
    ids=[f"{title}-{identifier}".replace(" ", "-") for title, identifier, _, _, _ in _NEAR_MISSES],
)
def test_near_miss_is_refused_never_substituted(
    act_title: str, identifier: str, pinpoint: str, expected: ResearchRefusalCode, why: str
) -> None:
    result = new_service().research(
        wa_query(act_title=act_title, provision_identifier=identifier, pinpoint=pinpoint)
    )

    # Near miss: {why}
    assert isinstance(result, ResearchRefused)
    assert result.code is expected
    assert not hasattr(result, "packet")
