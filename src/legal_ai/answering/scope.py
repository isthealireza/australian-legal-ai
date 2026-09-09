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


_INSTRUMENT = r"(?:contract|clause|agreement|document|term|deed|lease|policy|schedule|invoice)"

#: Asking the system to produce a document. Order matters: drafting is checked
#: first because "draft a letter ... citing section 22" also names a provision.
_DRAFTING_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bdraft\s+(?:me\s+)?(?:a|an|the)\b",
        r"\bwrite\s+(?:me\s+)?(?:a|an)\b[^.?!]*\b(?:letter|notice|agreement|contract|clause|"
        r"demand|deed|memo|submission|affidavit)\b",
        r"\bprepare\s+(?:me\s+)?(?:a|an|the)\b[^.?!]*\b(?:letter|notice|agreement|document|"
        r"demand|deed|submission|filing|affidavit)\b",
        r"\bletter\s+of\s+demand\b",
        r"\bmake\s+it\s+ready\s+to\s+send\b",
    )
)

#: Asking the system to review or advise on a supplied instrument.
_REVIEW_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        rf"\breview\s+(?:this|that|my|the)\s+{_INSTRUMENT}\b",
        r"\b(?:i\s*am|i'?m)\s+pasting\b",
        rf"\bhere\s+is\s+(?:my|the|our)\s+{_INSTRUMENT}\b",
        rf"\b{_INSTRUMENT}\s+(?:says|states|reads|stipulates|excludes|warrants)\b",
        r"\bshould\s+i\s+sign\b",
        r"\badvise\s+(?:my|the)\s+client\b",
        r"\bwhether\b[^.?!]{0,60}\b(?:enforceable|void|valid|binding)\b",
    )
)


def classify_request_kind(question: str) -> RequestKind:
    """Classify one question. RESEARCH unless it asks for review or drafting."""

    for pattern in _DRAFTING_PATTERNS:
        if pattern.search(question):
            return RequestKind.DOCUMENT_DRAFTING
    for pattern in _REVIEW_PATTERNS:
        if pattern.search(question):
            return RequestKind.DOCUMENT_REVIEW
    return RequestKind.RESEARCH
