"""Deterministic request-kind classification for the scope boundary.

MVP_ROADMAP section 11 puts contract review, document review/uploads, and court
document preparation out of scope by name. The service answers questions *about
recorded legislation*; it does not review a user's contract, assess a supplied
document, or draft one. Before this module that boundary held only because the
live answer model happened to decline such requests — a prompt, not a control.
The mock model answered them (LIVE_ADVERSARIAL_RUN.md S1-S4).

This module classifies the request kind from the question text alone, with a
small set of literal, case-insensitive patterns for the two out-of-scope shapes
the campaigns exercised: a request to review or advise on a supplied instrument,
and a request to draft or prepare one. It is deliberately conservative — it
matches the *act being asked for* (review this contract, draft a letter, should
I sign, my contract says, advise my client), not mere mentions of a contract —
so a legislation-research question that happens to name a contract is unaffected.
A miss fails open to the rest of the pipeline (retrieval, validation,
entailment); a match refuses before the model is ever called.
"""

from __future__ import annotations

import re
from enum import StrEnum


class RequestKind(StrEnum):
    """What the user is asking the system to do."""

    #: A question about recorded legislation. In scope.
    RESEARCH = "RESEARCH"
    #: Review, interpret, or advise on a supplied contract/document. Out of scope.
    DOCUMENT_REVIEW = "DOCUMENT_REVIEW"
    #: Draft or prepare a document, letter, or filing. Out of scope.
    DOCUMENT_DRAFTING = "DOCUMENT_DRAFTING"


_INSTRUMENT = (
    r"(?:contract|clause|agreement|document|paperwork|term|deed|lease|"
    r"policy|schedule|invoice|letter|notice|memo|affidavit|submission)"
)
#: A supplied instrument: the user's own, or one they attached/pasted. This
#: anchor is what keeps a mere mention of a contract from being read as a review
#: request — a signal only counts when it points at *their* document.
_SUPPLIED = rf"(?:my|our|this|that|the|your)\s+(?:attached\s+|above\s+)?{_INSTRUMENT}"

#: Verbs that ask the system to produce a document.
_DRAFT_VERB = r"(?:draft|write|prepare|draw\s+up|put\s+together|compose|knock\s+up)"
#: Verbs that ask the system to assess a supplied document.
_REVIEW_VERB = (
    r"(?:review|analyse|analyze|assess|check|vet|examine|"
    r"look\s+over|go\s+over|look\s+at|read\s+over)"
)
_DOC_NOUN = (
    r"(?:letter|notice|agreement|contract|clause|demand|deed|memo|"
    r"submission|affidavit|filing|response|schedule)"
)

#: Asking the system to produce a document. Order matters: drafting is checked
#: first because "draft a letter ... citing section 22" also names a provision.
_DRAFTING_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        rf"\b{_DRAFT_VERB}\s+(?:me\s+)?(?:a|an|the|my|this)\b[^.?!]*\b{_DOC_NOUN}\b",
        r"\bletter\s+of\s+demand\b",
        r"\bmake\s+it\s+ready\s+to\s+send\b",
        r"\bready\s+to\s+send\b",
    )
)

#: Asking the system to review or advise on a supplied instrument.
_REVIEW_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        rf"\b{_REVIEW_VERB}\s+{_SUPPLIED}\b",
        rf"\b{_REVIEW_VERB}\s+(?:this|that|the|it)\b[^.?!]{{0,40}}\b(?:for\s+me|for\s+compliance|"
        r"against\s+section|and\s+(?:tell|advise|let)\s+me)\b",
        r"\b(?:i\s*am|i'?m)\s+pasting\b",
        rf"\bhere\s+is\s+{_SUPPLIED}\b",
        rf"\b{_INSTRUMENT}\s+(?:says|states|reads|stipulates|excludes|warrants|provides\s+that)\b",
        r"\bshould\s+i\s+(?:sign|accept|agree\s+to)\b",
        r"\badvise\s+(?:my|the|our)\s+client\b",
        # Validity/enforceability, but only anchored to the user's own instrument
        # ("is my contract enforceable"), never a bare research question about
        # whether something is valid.
        rf"\b(?:is|are|whether)\b[^.?!]{{0,30}}\b(?:my|our|attached)\s+(?:\w+\s+){{0,3}}?"
        rf"{_INSTRUMENT}\b[^.?!]{{0,30}}\b(?:enforceable|void|valid|binding|lawful)\b",
        rf"\b(?:my|our|attached)\s+(?:\w+\s+){{0,3}}?{_INSTRUMENT}\b[^.?!]{{0,30}}\b"
        r"(?:enforceable|void|valid|binding|lawful)\b",
    )
)


def classify_request_kind(question: str) -> RequestKind:
    """Classify one question. RESEARCH unless it asks for review or drafting.

    Deterministic and conservative: it matches the *act being asked for* against
    a supplied instrument, not a mention of a contract, so it does not refuse a
    legislation-research question that discusses contracts, validity, or
    enforceability in the abstract. It is a pre-filter, not the only control: a
    request it does not match still faces retrieval, citation validation, and
    entailment, none of which this weakens. A novel paraphrase it misses is a
    false negative to close by adding a pattern, never a downstream bypass of the
    grounding checks.
    """

    for pattern in _DRAFTING_PATTERNS:
        if pattern.search(question):
            return RequestKind.DOCUMENT_DRAFTING
    for pattern in _REVIEW_PATTERNS:
        if pattern.search(question):
            return RequestKind.DOCUMENT_REVIEW
    return RequestKind.RESEARCH
