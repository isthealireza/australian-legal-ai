"""Shared builders for the Phase 5 grounded answering tests.

Packets are produced by the real Phase 4 service so that these tests exercise
the genuine contract rather than a hand-built imitation of it.
"""

from __future__ import annotations

import hashlib
from typing import Any

from legal_ai.answering.models import DraftCitation, DraftProposition, ModelDraft
from legal_ai.research.corpus import RecordedWaCorpus
from legal_ai.research.models import RecordedWaSource, WaEvidencePacket
from legal_ai.research.service import ResearchValidated, WaResearchService
from tests.research.conftest import (
    RECORDED_FIXTURE_ROOT,
    StubCorpus,
    query,
    recorded_query,
    recorded_source,
)
from tests.support.research_audit import InMemoryResearchAuditSink

#: A digest that is structurally valid but belongs to no recorded source.
FOREIGN_SHA256 = hashlib.sha256(b"a different document entirely").hexdigest()


def build_packet(**overrides: Any) -> WaEvidencePacket:
    """Return a validated, audited packet from the synthetic recorded source."""

    source: RecordedWaSource = recorded_source(**overrides)
    service = WaResearchService(
        corpus=StubCorpus(source),
        audit_sink=InMemoryResearchAuditSink(),
    )
    result = service.research(query(act_title=source.act_title or ""))
    assert isinstance(result, ResearchValidated), result
    return result.packet


def draft_for(packet: WaEvidencePacket, **citation_overrides: Any) -> ModelDraft:
    """Return a single-proposition draft citing the packet, with fields replaced."""

    fields: dict[str, Any] = {
        "source_id": packet.source_id,
        "provision_identifier": packet.provision_identifier,
        "pinpoint": packet.pinpoint,
        "sha256": packet.sha256,
        "quote": None,
    }
    fields.update(citation_overrides)
    return ModelDraft(
        propositions=(
            DraftProposition(
                statement="A driver must stop and give information.",
                citation=DraftCitation(**fields),
            ),
        )
    )


def build_recorded_packet() -> WaEvidencePacket:
    """Return a validated packet for the committed Road Traffic Act fixture."""

    service = WaResearchService(
        corpus=RecordedWaCorpus(RECORDED_FIXTURE_ROOT),
        audit_sink=InMemoryResearchAuditSink(),
    )
    result = service.research(recorded_query())
    assert isinstance(result, ResearchValidated), result
    return result.packet
