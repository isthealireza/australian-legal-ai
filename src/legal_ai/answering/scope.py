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
import unicodedata
from enum import StrEnum

#: Zero-width and word-joiner code points that carry no meaning but can be
#: inserted mid-word to defeat a literal match ("re​view my contract").
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)


def _normalise(question: str) -> str:
    """Fold obfuscation before matching: NFKC, strip zero-width, collapse space.

    NFKC folds compatibility homoglyphs and full-width forms to their plain
    equivalents; zero-width characters are removed; runs of whitespace collapse
    to one space. This does not decide scope, it only denies the cheapest ways to
    smuggle an out-of-scope phrasing past a literal pattern.
    """

    folded = unicodedata.normalize("NFKC", question).translate(_ZERO_WIDTH)
    return " ".join(folded.split())


class RequestKind(StrEnum):
    """What the user is asking the system to do."""

    #: A question about recorded legislation. In scope.
    RESEARCH = "RESEARCH"
    #: Review, interpret, or advise on a supplied contract/document. Out of scope.
    DOCUMENT_REVIEW = "DOCUMENT_REVIEW"
    #: Draft or prepare a document, letter, or filing. Out of scope.
    DOCUMENT_DRAFTING = "DOCUMENT_DRAFTING"


#: Private-instrument nouns. Deliberately excludes legislation terms (act,
#: section, provision, regulation, schedule of an Act): "review this Act" or
#: "review this section" is research, never document review.
_INSTRUMENT = (
    r"(?:contract|clause|agreement|paperwork|deed|lease|policy|"
    r"invoice|letter|notice|memo|affidavit|submission)"
)
#: A *supplied* instrument: the user's own, or one they attached/pasted. A signal
#: only counts when it points at their document, so a mere mention of a contract
#: in a legislation question is unaffected. "document"/"agreement"/"term" only
#: count with such an anchor, never bare.
_SUPPLIED = (
    rf"(?:my|our|this|that|the|your)\s+(?:\w+\s+){{0,2}}?(?:{_INSTRUMENT}|document|agreement|term)"
)

#: Verbs asking the system to produce a document.
_DRAFT_VERB = r"(?:draft|write|prepare|draw\s+up|put\s+together|compose|knock\s+up|generate)"
#: An imperative/request lead-in, so a drafting verb only fires when the system
#: is actually being asked to draft — not in "what are the requirements to
#: prepare a notice", where the verb is part of a research question.
_DRAFT_LEAD = (
    r"(?:^|[.?!]\s+|\b(?:please|pls|kindly|can\s+you|could\s+you|would\s+you|"
    r"will\s+you|help\s+me|i\s+need\s+you\s+to|i\s+want\s+you\s+to)\s+)"
)
_DOC_NOUN = (
    r"(?:letter|notice|agreement|contract|clause|demand|deed|memo|"
    r"submission|affidavit|filing|response)"
)
#: Verbs asking the system to assess a supplied document.
_REVIEW_VERB = (
    r"(?:review|analyse|analyze|assess|check|vet|examine|"
    r"look\s+over|go\s+over|take\s+a\s+look\s+at|have\s+a\s+look\s+at|read\s+over)"
)

#: Asking the system to produce a document. Drafting is checked first because a
#: drafting request ("draft a letter ... citing section 22") also names a
#: provision. The verb must be in an imperative/request position.
_DRAFTING_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        rf"{_DRAFT_LEAD}{_DRAFT_VERB}\s+(?:me\s+)?(?:a|an|the|my|this)\b[^.?!]*\b{_DOC_NOUN}\b",
        r"\bmake\s+it\s+ready\s+to\s+send\b",
    )
)

#: Asking the system to review or advise on a supplied instrument. Every pattern
#: is anchored to the user's own document or an explicit advice-on-instrument
#: request; none fires on a legislation-research phrasing.
_REVIEW_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        rf"\b{_REVIEW_VERB}\s+{_SUPPLIED}\b",
        r"\b(?:i\s*am|i'?m)\s+pasting\b",
        rf"\bhere\s+is\s+{_SUPPLIED}\b",
        # A quoted instrument, but only the user's own ("my … contract says"),
        # never "the contract says" in an abstract legislation question.
        rf"\b(?:my|our|your)\b[^.?!]{{0,30}}\b{_INSTRUMENT}\s+"
        r"(?:says|states|reads|stipulates|excludes|warrants|provides\s+that)\b",
        r"\b(?:should|can|may|could)\s+i\s+(?:sign|accept|agree\s+to)\b",
        r"\badvise\s+(?:my|the|our)\s+client\b",
        rf"\badvise\s+me\s+(?:on|about)\s+(?:my|this|that|the|our)\s+(?:attached\s+)?"
        rf"(?:{_INSTRUMENT}|document|agreement|term)\b",
        rf"\bwhat\s+(?:do\s+you\s+think|are\s+your\s+thoughts|is\s+your\s+(?:view|opinion))\s+"
        rf"(?:of|about|on)\s+(?:my|our|this|that|the)\s+(?:attached\s+)?"
        rf"(?:{_INSTRUMENT}|document|agreement|term)\b",
        # Validity/enforceability, anchored to the user's own instrument only
        # ("is my contract enforceable"), never a bare research question about
        # whether some provision or claim is valid.
        rf"\b(?:my|our|attached)\s+(?:\w+\s+){{0,3}}?(?:{_INSTRUMENT}|agreement)\b"
        rf"[^.?!]{{0,30}}\b(?:enforceable|void|valid|binding|lawful)\b",
        rf"\b(?:enforceable|void|valid|binding|lawful)\b[^.?!]{{0,30}}\b(?:my|our|attached)\s+"
        rf"(?:\w+\s+){{0,3}}?(?:{_INSTRUMENT}|agreement)\b",
        # Subjective review terms (fair/reasonable/okay) are never legislative
        # research language, so they may anchor to a deictic instrument too.
        rf"\b(?:my|our|this|that|the|attached)\s+(?:\w+\s+){{0,3}}?(?:{_INSTRUMENT}|agreement)\b"
        rf"[^.?!]{{0,30}}\b(?:fair|reasonable|okay|acceptable|a\s+good\s+deal)\b",
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

    normalised = _normalise(question)
    for pattern in _DRAFTING_PATTERNS:
        if pattern.search(normalised):
            return RequestKind.DOCUMENT_DRAFTING
    for pattern in _REVIEW_PATTERNS:
        if pattern.search(normalised):
            return RequestKind.DOCUMENT_REVIEW
    return RequestKind.RESEARCH
