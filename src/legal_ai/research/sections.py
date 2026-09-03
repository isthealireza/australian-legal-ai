"""The mandatory verification gate for recorded section body text.

ADR 0014 recorded section body text as data and deliberately left its integrity
unverified: `_load_sections` stores `text_sha256` without recomputing it, and
`verified=False` is the default with no consumer to enforce it. That was safe
only because nothing consumed section text. This module is the gate that must
sit in front of the first consumer.

`verify_section` is the sanctioned path from a `RecordedWaSource` to text a
consumer may read. It is not a technical monopoly — `RecordedSection` and
`RecordedWaSource.sections` remain public, and the tests read them directly —
so it is enforced by review and by the fact that no consumer exists yet.

The checks run in a fixed order and any failure is total: a typed refusal code,
never a partial result and never the text.

1. the companion file must claim the same document as the source it came with;
2. the requested identifier must resolve to exactly one section;
3. that identifier must be declared by exactly one manifest provision;
4. `verified` must be exactly `True`;
5. the recomputed digest must equal the recorded digest.

Order matters. A file that describes a different document is refused before any
record inside it is examined, and `verified` is checked before the digest so
that a section nobody has verified is refused on that ground rather than on an
incidental digest result.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, ConfigDict, model_validator

from .corpus import normalize_for_match
from .models import RecordedSection, RecordedWaSource
from .types import ResearchRefusalCode

_STRICT = ConfigDict(extra="forbid", strict=True, frozen=True)


def section_text_digest(text: str) -> str:
    """Return the digest convention ADR 0014 §3 fixed for section text."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class VerifiedSection(BaseModel):
    """Section body text returned by `verify_section`.

    Be precise about what this type proves, because an overclaim here would be
    worse than no claim at all.

    **Self-evident, on every instance however built.** The text matches
    `text_sha256`. The model validator recomputes it, so direct construction and
    `model_validate` both raise on a mismatch.

    **Not self-evident.** That the companion file was bound to this document,
    that the manifest declares this identifier, and that a human set `verified`
    to exactly `True`. None of those three are properties of the fields carried
    here — `verified` and the binding belong to the source, not the section — so
    they cannot be re-derived from an instance. They are proven only by having
    come from `verify_section`, which is why it is the sanctioned constructor
    and why a hand-built instance means strictly less than one it returned.

    **Two Pydantic bypasses.** Neither `model_copy` nor `model_construct` runs
    validators; `model_construct` is a documented validation bypass, so it can
    produce an instance whose digest does not match at all. Both are pinned by
    tests so the limit stays visible rather than being assumed away.

    A future consumer must therefore accept these only from `verify_section` and
    must not treat the type alone as authority.
    """

    model_config = _STRICT

    source_id: str
    identifier: str
    heading: str | None
    text: str
    text_sha256: str

    @model_validator(mode="after")
    def _recheck(self) -> VerifiedSection:
        if section_text_digest(self.text) != self.text_sha256:
            raise ValueError("section text does not match its recorded digest")
        return self


def _binding_refusal(source: RecordedWaSource) -> ResearchRefusalCode | None:
    """Refuse unless the companion file claims this exact document."""

    declared_source_id = source.sections_source_id
    declared_digest = source.sections_source_document_sha256
    if declared_source_id is None or declared_digest is None:
        return ResearchRefusalCode.SECTION_SOURCE_MISMATCH
    if declared_source_id != source.source_id or declared_digest != source.sha256:
        return ResearchRefusalCode.SECTION_SOURCE_MISMATCH
    return None


def _declared_by_manifest(source: RecordedWaSource, identifier: str) -> bool:
    """Whether exactly one manifest provision declares this identifier."""

    wanted = normalize_for_match(identifier)
    declaring = [
        provision
        for provision in source.provisions
        if wanted
        in {
            normalize_for_match(provision.identifier),
            normalize_for_match(provision.pinpoint),
        }
    ]
    return len(declaring) == 1


def _matching_sections(source: RecordedWaSource, identifier: str) -> tuple[RecordedSection, ...]:
    wanted = normalize_for_match(identifier)
    return tuple(
        section for section in source.sections if normalize_for_match(section.identifier) == wanted
    )


def verify_section(
    *,
    source: RecordedWaSource,
    identifier: str,
) -> VerifiedSection | ResearchRefusalCode:
    """Return verified section text for `identifier`, or the reason to refuse.

    Every failure is a typed refusal. Nothing partial and no text is returned on
    any failing path.
    """

    binding = _binding_refusal(source)
    if binding is not None:
        return binding

    matches = _matching_sections(source, identifier)
    if not matches:
        return ResearchRefusalCode.SECTION_TEXT_MISSING
    if len(matches) > 1:
        return ResearchRefusalCode.SECTION_AMBIGUOUS
    section = matches[0]

    if not _declared_by_manifest(source, section.identifier):
        return ResearchRefusalCode.SECTION_NOT_IN_MANIFEST

    if section.verified is not True:
        return ResearchRefusalCode.SECTION_NOT_VERIFIED

    if section_text_digest(section.text) != section.text_sha256:
        return ResearchRefusalCode.SECTION_TEXT_HASH_MISMATCH

    source_id = source.source_id
    if source_id is None:
        return ResearchRefusalCode.SECTION_SOURCE_MISMATCH

    return VerifiedSection(
        source_id=source_id,
        identifier=section.identifier,
        heading=section.heading,
        text=section.text,
        text_sha256=section.text_sha256,
    )
