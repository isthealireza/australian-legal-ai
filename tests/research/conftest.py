"""Shared builders and corpus doubles for the Phase 4 WA research tests.

Synthetic records are used for every negative and adversarial case so that the
recorded fixture bytes on `main` are never modified.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any

from legal_ai.research.corpus import normalize_for_match
from legal_ai.research.errors import AmbiguousSelection, RecordedCorpusError
from legal_ai.research.models import RecordedProvision, RecordedWaSource, ResearchQuery

RECORDED_FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "wa_legislation"
RECORDED_ACT_TITLE = "Road Traffic Act 1974"
RECORDED_SHA256 = "61dbca2d8eddc33a3ebc759b8759886192efaa8b09440089541efd35ed19c525"
RECORDED_SOURCE_ID = "wa_legislation:road_traffic_act_1974:consolidated:14-t0-00"

SYNTHETIC_CONTENT = (
    b"55. Driver in incident occasioning property damage to stop and give information."
)
SYNTHETIC_SHA256 = hashlib.sha256(SYNTHETIC_CONTENT).hexdigest()

_BASE_SOURCE = RecordedWaSource(
    source_id="wa_legislation:synthetic_act_1974:consolidated:1-a0-00",
    source_system="wa_legislation",
    jurisdiction="WA",
    act_title="Synthetic Act 1974",
    act_jurisdiction="WA",
    act_number="001 of 1974",
    official_source_url="https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_s1.html",
    provisions=(
        RecordedProvision(identifier="s 55", pinpoint="section 55", heading="Synthetic heading"),
    ),
    source_version="1-a0-00",
    compilation_date="2025-01-10",
    status_currency="Current",
    status_in_force=True,
    status_date="2025-01-10",
    retrieved_at="2026-08-11T10:27:03Z",
    sha256=SYNTHETIC_SHA256,
    source_content=SYNTHETIC_CONTENT,
)


def recorded_source(**overrides: Any) -> RecordedWaSource:
    """Return a valid synthetic recorded source with the given fields replaced."""

    return replace(_BASE_SOURCE, **overrides)


def query(**overrides: Any) -> ResearchQuery:
    """Return a query that matches the synthetic source unless overridden."""

    fields: dict[str, Any] = {
        "jurisdiction": "WA",
        "act_title": "Synthetic Act 1974",
        "provision_identifier": "s 55",
        "pinpoint": "section 55",
    }
    fields.update(overrides)
    return ResearchQuery(**fields)


def recorded_query(**overrides: Any) -> ResearchQuery:
    """Return a query against the recorded Road Traffic Act 1974 (WA) fixture."""

    fields: dict[str, Any] = {
        "jurisdiction": "WA",
        "act_title": RECORDED_ACT_TITLE,
        "provision_identifier": "s 55",
        "pinpoint": "section 55",
    }
    fields.update(overrides)
    return ResearchQuery(**fields)


class StubCorpus:
    """In-memory corpus double with the same selection semantics as the real one."""

    def __init__(self, *sources: RecordedWaSource) -> None:
        self._sources = sources

    def select(self, query: ResearchQuery) -> RecordedWaSource | None:
        wanted = normalize_for_match(query.act_title)
        matches = [
            source
            for source in self._sources
            if normalize_for_match(source.act_title or "") == wanted
        ]
        if not matches:
            return None
        if len(matches) > 1:
            raise AmbiguousSelection("more than one recorded source matched")
        return matches[0]


class UnreadableCorpus:
    """A corpus whose recorded fixture cannot be loaded."""

    def select(self, query: ResearchQuery) -> RecordedWaSource | None:
        del query
        raise RecordedCorpusError("recorded content could not be read")
