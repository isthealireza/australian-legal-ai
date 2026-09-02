"""Deterministic citation validation (MVP_ROADMAP section 8, levels 1 and 2).

Every check here is exact, total, and independent of any model. A draft is
either fully validated or the whole answer is refused: there is no partial
acceptance, and no proposition survives on its own.
"""

from __future__ import annotations

from ..research.models import WaEvidencePacket
from .models import (
    MAX_PROPOSITIONS,
    Citation,
    DraftCitation,
    ModelDraft,
    Proposition,
)
from .types import AnswerRefusalCode


def _validate_citation(
    citation: DraftCitation,
    packet: WaEvidencePacket,
    provision_text: bytes | None,
) -> Citation | AnswerRefusalCode:
    """Check one asserted citation against the exact packet it claims."""

    # Level 1 — existence: the citation must name the packet actually retrieved.
    if citation.source_id != packet.source_id:
        return AnswerRefusalCode.CITATION_SOURCE_UNKNOWN
    if citation.sha256 != packet.sha256:
        return AnswerRefusalCode.CITATION_DIGEST_MISMATCH

    # Level 2 — pinpoint integrity: the provision and pinpoint must be the ones
    # whose bytes were verified, not a neighbouring or invented provision.
    if citation.provision_identifier != packet.provision_identifier:
        return AnswerRefusalCode.CITATION_PROVISION_MISMATCH
    if citation.pinpoint != packet.pinpoint:
        return AnswerRefusalCode.CITATION_PINPOINT_MISMATCH

    # A quote is optional, but a quote that is not literally present in the
    # verified bytes is a fabrication and refuses the entire answer. When
    # digest-chained provision text is available the quote is checked against
    # that exact text; otherwise it is checked against the whole instrument.
    if citation.quote is not None:
        haystack = provision_text if provision_text is not None else packet.source_content
        if citation.quote.encode("utf-8") not in haystack:
            return AnswerRefusalCode.QUOTE_NOT_IN_SOURCE

    return Citation(
        source_id=packet.source_id,
        act_title=packet.act.title,
        provision_identifier=packet.provision_identifier,
        pinpoint=packet.pinpoint,
        source_version=packet.source_version,
        compilation_date=packet.compilation_date,
        official_source_url=packet.official_source_url,
        sha256=packet.sha256,
        quote=citation.quote,
    )


def validate_draft(
    draft: ModelDraft,
    packet: WaEvidencePacket,
    provision_text: bytes | None = None,
) -> tuple[Proposition, ...] | AnswerRefusalCode:
    """Return every validated proposition, or the first typed refusal code."""

    if not draft.propositions:
        return AnswerRefusalCode.NO_PROPOSITIONS
    if len(draft.propositions) > MAX_PROPOSITIONS:
        return AnswerRefusalCode.MODEL_OUTPUT_MALFORMED

    validated: list[Proposition] = []
    for proposition in draft.propositions:
        citation = _validate_citation(proposition.citation, packet, provision_text)
        if isinstance(citation, AnswerRefusalCode):
            return citation
        validated.append(Proposition(statement=proposition.statement, citation=citation))
    return tuple(validated)
