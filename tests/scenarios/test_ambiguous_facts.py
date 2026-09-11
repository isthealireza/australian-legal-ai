"""FAMILY 4 — AMBIGUOUS FACTS.

Dates, parties or legal category are missing or under-specified. The pipeline
has no dialogue: its "ask" state is a typed refusal that an upstream UI layer
can turn into a clarifying question. The invariant asserted here is that the
pipeline never guesses — never silently picks an Act, a candidate source, a
neighbouring provision, or a later version — and never returns a packet when
the facts do not determine a recorded citation.

Grounding: each scenario names the exact fixture (or fixtures) it would have
to choose between, and the expected outcome is the refusal code the
deterministic pipeline is proven to emit (service.py / corpus.py /
validation.py code paths).
"""

from __future__ import annotations

from legal_ai.research.service import ResearchRefused, ResearchValidated, WaResearchService
from legal_ai.research.types import ResearchRefusalCode
from tests.research.conftest import StubCorpus, recorded_source
from tests.scenarios.conftest import new_service, wa_query
from tests.support.research_audit import InMemoryResearchAuditSink


def test_missing_act_year_is_refused_not_assumed() -> None:
    # A user problem about the fitness of purchased goods, identifying the Act
    # only as "Sale of Goods Act" with no year. Two recorded WA Acts could be
    # meant by a user, but only "Sale of Goods Act 1895" is recorded; the exact
    # title-contract still refuses rather than assume the 1895 recording.
    result = new_service().research(
        wa_query(
            act_title="Sale of Goods Act",
            provision_identifier="s 13",
            pinpoint="section 13",
        )
    )

    assert isinstance(result, ResearchRefused)
    assert result.code is ResearchRefusalCode.RETRIEVAL_MISSING
    assert not hasattr(result, "packet")


def test_ambiguous_selection_between_two_candidates_is_refused() -> None:
    # Two recorded sources both carry the same title. No deterministic
    # selection exists, and the pipeline must refuse rather than pick one.
    source = recorded_source(act_title="Road Traffic Act 1974")
    twin = recorded_source(
        act_title="Road Traffic Act 1974",
        source_id="wa_legislation:road_traffic_act_1974:consolidated:99-z0-00",
    )
    service = WaResearchService(
        corpus=StubCorpus(source, twin),
        audit_sink=InMemoryResearchAuditSink(),
    )

    result = service.research(wa_query(act_title="Road Traffic Act 1974"))

    assert isinstance(result, ResearchRefused)
    assert result.code is ResearchRefusalCode.SELECTION_AMBIGUOUS
    assert not hasattr(result, "packet")


def test_facts_straddling_two_recorded_provisions_refuse_instead_of_subbing() -> None:
    # The recorded fixture records s 55 (property damage stop-and-give-
    # information) and s 56 (report to police) as separate pinpoints. A problem
    # that spans both (property damage AND a police-report expectation) does
    # not determine which section is meant. Asking about "s 55" with the
    # "section 56" pinpoint is refused; the neighbouring provision is never
    # silently substituted.
    result = new_service().research(
        wa_query(
            act_title="Road Traffic Act 1974",
            provision_identifier="s 55",
            pinpoint="section 56",
        )
    )

    assert isinstance(result, ResearchRefused)
    assert result.code is ResearchRefusalCode.PINPOINT_MISMATCH
    assert not hasattr(result, "packet")


def test_a_date_dependent_question_is_answered_only_from_the_recorded_version() -> None:
    # The recorded RTA snapshot is a point-in-time fixture (compilation
    # 2025-01-10, status date 2025-01-10, retrieved 2026-08-11). A question
    # about what the Act requires "after later amendments" cannot consult a
    # later version: the pipeline answers only from the recorded version and
    # the packet's provenance makes the snapshot boundary explicit. It never
    # invents a later compilation or a renumbered provision.
    result = new_service().research(
        wa_query(
            act_title="Road Traffic Act 1974",
            provision_identifier="s 55",
            pinpoint="section 55",
        )
    )

    assert isinstance(result, ResearchValidated)
    assert result.packet.source_version == "14-t0-00"
    assert str(result.packet.compilation_date) == "2025-01-10"
    assert str(result.packet.status_date) == "2025-01-10"
    assert str(result.packet.retrieved_at.date()) == "2026-08-11"
