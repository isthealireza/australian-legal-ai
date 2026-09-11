"""Golden regression harness for Road Traffic Act 1974 (WA) ss 55-56.

Every later corpus-expansion phase makes the same safety claim: that adding
provisions, sections or Acts leaves ss 55-56 exactly as they are. This module is
that claim, written down once, before anything is added.

It is deliberately blunt. Each frozen value is a literal in the GOLDEN CONSTANTS
block below, so a change in recorded behaviour fails here with the old and new
values side by side rather than being absorbed by a helper.

Scope and safety:

- Read-only over the committed fixture. No network, no clock, no database, no
  model, no provider, and no write to any fixture file.
- No statutory text appears here. Section body text is frozen by its SHA-256 and
  its exact character length, which pins the bytes without reproducing them.
- These assertions are additive. They duplicate some coverage in
  `test_recorded_fixture.py` and `test_sections.py` on purpose: those modules
  test behaviour, this one refuses drift.

See `docs/adr/0017-wa-corpus-expansion-invariants.md`.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime

import pytest

from legal_ai.research.corpus import RecordedWaCorpus
from legal_ai.research.models import RecordedWaSource, WaEvidencePacket
from legal_ai.research.service import ResearchRefused, ResearchValidated, WaResearchService
from legal_ai.research.types import (
    LegalStatus,
    ResearchAuditResult,
    ResearchOutcome,
    ResearchRefusalCode,
)
from tests.research.conftest import RECORDED_FIXTURE_ROOT, recorded_query
from tests.support.research_audit import InMemoryResearchAuditSink

# ---------------------------------------------------------------------------
# GOLDEN CONSTANTS — do not edit without an owner-approved bounded task.
#
# Every value below is the recorded state of the Road Traffic Act 1974 (WA)
# consolidated fixture at version 14-t0-00. A failure here means recorded
# behaviour moved. That is either a defect or a deliberate, separately
# authorised corpus change; it is never something to "fix" by editing this
# block to match.
# ---------------------------------------------------------------------------

GOLDEN_SOURCE_ID = "wa_legislation:road_traffic_act_1974:consolidated:14-t0-00"
GOLDEN_SOURCE_SYSTEM = "wa_legislation"
GOLDEN_JURISDICTION = "WA"
GOLDEN_ACT_TITLE = "Road Traffic Act 1974"
GOLDEN_ACT_NUMBER = "059 of 1974"
GOLDEN_OFFICIAL_SOURCE_URL = (
    "https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_a703.html&view=consolidated"
)

GOLDEN_SOURCE_VERSION = "14-t0-00"
GOLDEN_COMPILATION_DATE = date(2025, 1, 10)
GOLDEN_STATUS_DATE = date(2025, 1, 10)
GOLDEN_LEGAL_STATUS = LegalStatus.IN_FORCE
GOLDEN_RETRIEVED_AT = datetime(2026, 8, 11, 10, 27, 3, tzinfo=UTC)

GOLDEN_PDF_SHA256 = "61dbca2d8eddc33a3ebc759b8759886192efaa8b09440089541efd35ed19c525"
GOLDEN_PDF_BYTE_LENGTH = 1_294_287

GOLDEN_S55_IDENTIFIER = "s 55"
GOLDEN_S55_PINPOINT = "section 55"
GOLDEN_S55_HEADING = "Driver in incident occasioning property damage to stop and give information"
GOLDEN_S56_IDENTIFIER = "s 56"
GOLDEN_S56_PINPOINT = "section 56"
GOLDEN_S56_HEADING = (
    "Driver in incident occasioning bodily harm or property damage to report incident to police"
)

GOLDEN_PROVISION_COUNT = 2

# Section body text is frozen by digest and length only. The text itself is
# never reproduced here: the digest pins the exact bytes, and the length makes a
# digest collision or a silently truncated record visible.
GOLDEN_SECTION_COUNT = 2
GOLDEN_S55_TEXT_SHA256 = "b7a3ade27ed1f803955d801e12e3704172582b3239eee12fc2e2c4d5ae8a72f9"
GOLDEN_S55_TEXT_LENGTH = 1763
GOLDEN_S56_TEXT_SHA256 = "6e201142fb8310f420475524d3c43a1d534a44405ac67b33994eb2bdb0995dbf"
GOLDEN_S56_TEXT_LENGTH = 3523
GOLDEN_SECTIONS_VERIFIED = False

# Refusals that must keep their exact typed code as the corpus grows.
GOLDEN_REFUSALS: tuple[tuple[str, str, ResearchRefusalCode], ...] = (
    ("s 54", "section 54", ResearchRefusalCode.CITATION_NOT_FOUND),
    ("s 57", "section 57", ResearchRefusalCode.CITATION_NOT_FOUND),
    ("s 55A", "section 55A", ResearchRefusalCode.CITATION_NOT_FOUND),
    ("s 999", "section 999", ResearchRefusalCode.CITATION_NOT_FOUND),
    ("s 55", "section 56", ResearchRefusalCode.PINPOINT_MISMATCH),
    ("s 56", "section 55", ResearchRefusalCode.PINPOINT_MISMATCH),
)

# ---------------------------------------------------------------------------
# End of GOLDEN CONSTANTS.
# ---------------------------------------------------------------------------

_GOLDEN_PROVISIONS = (
    (GOLDEN_S55_IDENTIFIER, GOLDEN_S55_PINPOINT, GOLDEN_S55_HEADING),
    (GOLDEN_S56_IDENTIFIER, GOLDEN_S56_PINPOINT, GOLDEN_S56_HEADING),
)

_GOLDEN_SECTIONS = (
    (GOLDEN_S55_IDENTIFIER, GOLDEN_S55_HEADING, GOLDEN_S55_TEXT_SHA256, GOLDEN_S55_TEXT_LENGTH),
    (GOLDEN_S56_IDENTIFIER, GOLDEN_S56_HEADING, GOLDEN_S56_TEXT_SHA256, GOLDEN_S56_TEXT_LENGTH),
)


def _corpus() -> RecordedWaCorpus:
    return RecordedWaCorpus(RECORDED_FIXTURE_ROOT)


def _source() -> RecordedWaSource:
    source = _corpus().select(recorded_query())
    assert source is not None, "the recorded Road Traffic Act 1974 fixture must be selectable"
    return source


def _validate(identifier: str, pinpoint: str) -> tuple[object, InMemoryResearchAuditSink]:
    sink = InMemoryResearchAuditSink()
    service = WaResearchService(corpus=_corpus(), audit_sink=sink)
    result = service.research(recorded_query(provision_identifier=identifier, pinpoint=pinpoint))
    return result, sink


def _packet(identifier: str, pinpoint: str) -> WaEvidencePacket:
    result, _ = _validate(identifier, pinpoint)
    assert isinstance(result, ResearchValidated), (
        f"{identifier}/{pinpoint} must still validate, got {result!r}"
    )
    return result.packet


# ---------------------------------------------------------------------------
# Source-level golden state
# ---------------------------------------------------------------------------


def test_fixture_bytes_are_unchanged() -> None:
    """The recorded PDF is byte-identical to the capture ADR 0013 recorded."""

    pdf = (
        RECORDED_FIXTURE_ROOT
        / "road_traffic_act_1974"
        / "road_traffic_act_1974_consolidated_14-t0-00.pdf"
    )
    content = pdf.read_bytes()
    assert len(content) == GOLDEN_PDF_BYTE_LENGTH
    assert hashlib.sha256(content).hexdigest() == GOLDEN_PDF_SHA256


def test_selected_source_identity_is_unchanged() -> None:
    source = _source()
    assert source.source_id == GOLDEN_SOURCE_ID
    assert source.source_system == GOLDEN_SOURCE_SYSTEM
    assert source.jurisdiction == GOLDEN_JURISDICTION
    assert source.act_title == GOLDEN_ACT_TITLE
    assert source.act_jurisdiction == GOLDEN_JURISDICTION
    assert source.act_number == GOLDEN_ACT_NUMBER
    assert source.official_source_url == GOLDEN_OFFICIAL_SOURCE_URL
    assert source.sha256 == GOLDEN_PDF_SHA256


def test_recorded_provision_list_is_exactly_ss_55_and_56() -> None:
    """A new provision must not be added to this Act without a new golden value."""

    source = _source()
    assert len(source.provisions) == GOLDEN_PROVISION_COUNT
    recorded = tuple(
        (provision.identifier, provision.pinpoint, provision.heading)
        for provision in source.provisions
    )
    assert recorded == _GOLDEN_PROVISIONS


# ---------------------------------------------------------------------------
# Packet-level golden state
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("identifier", "pinpoint", "heading"),
    [
        (GOLDEN_S55_IDENTIFIER, GOLDEN_S55_PINPOINT, GOLDEN_S55_HEADING),
        (GOLDEN_S56_IDENTIFIER, GOLDEN_S56_PINPOINT, GOLDEN_S56_HEADING),
    ],
)
def test_packet_fields_are_frozen(identifier: str, pinpoint: str, heading: str) -> None:
    packet = _packet(identifier, pinpoint)

    assert packet.source_id == GOLDEN_SOURCE_ID
    assert packet.source_system == GOLDEN_SOURCE_SYSTEM
    assert packet.jurisdiction == GOLDEN_JURISDICTION
    assert packet.act.title == GOLDEN_ACT_TITLE
    assert packet.act.jurisdiction == GOLDEN_JURISDICTION
    assert packet.act.act_number == GOLDEN_ACT_NUMBER
    assert packet.official_source_url == GOLDEN_OFFICIAL_SOURCE_URL

    assert packet.provision_identifier == identifier
    assert packet.pinpoint == pinpoint
    assert packet.provision_heading == heading

    assert packet.source_version == GOLDEN_SOURCE_VERSION
    assert packet.compilation_date == GOLDEN_COMPILATION_DATE
    assert packet.legal_status is GOLDEN_LEGAL_STATUS
    assert packet.status_date == GOLDEN_STATUS_DATE
    assert packet.retrieved_at == GOLDEN_RETRIEVED_AT

    assert packet.sha256 == GOLDEN_PDF_SHA256
    assert len(packet.source_content) == GOLDEN_PDF_BYTE_LENGTH
    assert hashlib.sha256(packet.source_content).hexdigest() == GOLDEN_PDF_SHA256
    assert packet.audit_result is ResearchAuditResult.RECORDED


def test_both_provisions_share_one_source_and_stay_distinct() -> None:
    """Expansion must not merge, split, or cross-wire the two provisions."""

    s55 = _packet(GOLDEN_S55_IDENTIFIER, GOLDEN_S55_PINPOINT)
    s56 = _packet(GOLDEN_S56_IDENTIFIER, GOLDEN_S56_PINPOINT)

    assert s55.source_id == s56.source_id
    assert s55.sha256 == s56.sha256
    assert s55.provision_identifier != s56.provision_identifier
    assert s55.pinpoint != s56.pinpoint
    assert s55.provision_heading != s56.provision_heading


# ---------------------------------------------------------------------------
# Audit-level golden state
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("identifier", "pinpoint"),
    [
        (GOLDEN_S55_IDENTIFIER, GOLDEN_S55_PINPOINT),
        (GOLDEN_S56_IDENTIFIER, GOLDEN_S56_PINPOINT),
    ],
)
def test_one_validated_audit_event_per_evaluation(identifier: str, pinpoint: str) -> None:
    _, sink = _validate(identifier, pinpoint)

    assert len(sink.events) == 1
    event = sink.events[0]
    assert event.outcome is ResearchOutcome.VALIDATED
    assert event.source_id == GOLDEN_SOURCE_ID
    assert event.sha256 == GOLDEN_PDF_SHA256
    assert event.refusal_code is None
    assert event.requested_jurisdiction == GOLDEN_JURISDICTION
    assert event.requested_act_title == GOLDEN_ACT_TITLE
    assert event.requested_provision_identifier == identifier
    assert event.requested_pinpoint == pinpoint


# ---------------------------------------------------------------------------
# Section-record golden state
# ---------------------------------------------------------------------------


def test_recorded_sections_are_exactly_ss_55_and_56() -> None:
    source = _source()
    assert len(source.sections) == GOLDEN_SECTION_COUNT
    recorded = tuple(
        (section.identifier, section.heading, section.text_sha256, len(section.text))
        for section in source.sections
    )
    assert recorded == _GOLDEN_SECTIONS


def test_recorded_section_text_matches_the_golden_digest() -> None:
    """Pins the bytes without reproducing the text: I8 in ADR 0017.

    The digest is recomputed from the text and compared to the **golden
    literal**, not to the fixture's own recorded `text_sha256`. Comparing a
    fixture value to itself would still pass if the text and its recorded digest
    were changed together, which is exactly the drift this module exists to
    catch.
    """

    expected = {
        GOLDEN_S55_IDENTIFIER: GOLDEN_S55_TEXT_SHA256,
        GOLDEN_S56_IDENTIFIER: GOLDEN_S56_TEXT_SHA256,
    }
    sections = _source().sections
    assert {section.identifier for section in sections} == set(expected)
    for section in sections:
        computed = hashlib.sha256(section.text.encode("utf-8")).hexdigest()
        assert computed == expected[section.identifier]
        # The fixture must also agree with itself; a mismatch here means the
        # recorded digest and the recorded text have diverged.
        assert section.text_sha256 == expected[section.identifier]


def test_recorded_sections_remain_unverified() -> None:
    """`verified` is the human legal-content gate. Nothing automatic may flip it."""

    for section in _source().sections:
        assert section.verified is GOLDEN_SECTIONS_VERIFIED


def test_every_recorded_section_binds_to_a_recorded_provision() -> None:
    """Section identifiers and manifest provision identifiers must agree exactly."""

    source = _source()
    provision_identifiers = {provision.identifier for provision in source.provisions}
    section_identifiers = {section.identifier for section in source.sections}
    assert section_identifiers == provision_identifiers


# ---------------------------------------------------------------------------
# Refusal golden state
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("identifier", "pinpoint", "code"), GOLDEN_REFUSALS)
def test_refusal_codes_are_frozen(
    identifier: str, pinpoint: str, code: ResearchRefusalCode
) -> None:
    result, sink = _validate(identifier, pinpoint)

    assert isinstance(result, ResearchRefused), f"{identifier}/{pinpoint} must refuse"
    assert result.code is code
    assert not hasattr(result, "packet")

    assert len(sink.events) == 1
    event = sink.events[0]
    assert event.outcome is ResearchOutcome.REFUSED
    assert event.refusal_code is code
    assert event.source_id is None
    assert event.sha256 is None
    assert event.requested_jurisdiction == GOLDEN_JURISDICTION
    assert event.requested_act_title == GOLDEN_ACT_TITLE
    assert event.requested_provision_identifier == identifier
    assert event.requested_pinpoint == pinpoint


def test_an_act_absent_from_the_corpus_refuses_as_missing_retrieval() -> None:
    """Uses a title that cannot exist, so corpus growth never invalidates it.

    This previously named the Sale of Goods Act 1895, which was absent when the
    harness was written and has since been recorded on `main`. The assertion was
    about an *absent* Act, so the example was the stale part, not the intent.
    """

    sink = InMemoryResearchAuditSink()
    service = WaResearchService(corpus=_corpus(), audit_sink=sink)
    result = service.research(recorded_query(act_title="No Such Act 2099"))

    assert isinstance(result, ResearchRefused)
    assert result.code is ResearchRefusalCode.RETRIEVAL_MISSING


def test_a_non_wa_jurisdiction_still_refuses() -> None:
    sink = InMemoryResearchAuditSink()
    service = WaResearchService(corpus=_corpus(), audit_sink=sink)
    result = service.research(recorded_query(jurisdiction="NSW"))

    assert isinstance(result, ResearchRefused)
    assert result.code is ResearchRefusalCode.JURISDICTION_MISMATCH


# ---------------------------------------------------------------------------
# No-drift behaviour
# ---------------------------------------------------------------------------


def test_repeated_evaluation_is_identical() -> None:
    """Repeatability only. The literal freezing is done by the tests above.

    This compares two evaluations to each other, so it would still pass after a
    self-consistent fixture change. It is here to catch nondeterminism, not
    drift, and it is anchored to one golden literal so it cannot pass against a
    wholly different source.
    """

    first = _packet(GOLDEN_S55_IDENTIFIER, GOLDEN_S55_PINPOINT)
    second = _packet(GOLDEN_S55_IDENTIFIER, GOLDEN_S55_PINPOINT)
    assert first == second
    assert first.sha256 == GOLDEN_PDF_SHA256


def test_fresh_corpus_instances_agree() -> None:
    """Loading order and instance identity must not affect the recorded result.

    Relational, like the test above, and anchored to a golden literal.
    """

    left = _corpus().select(recorded_query())
    right = _corpus().select(recorded_query())
    assert left == right
    assert left is not right
    assert left is not None
    assert left.source_id == GOLDEN_SOURCE_ID
