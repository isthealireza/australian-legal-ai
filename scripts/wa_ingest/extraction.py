"""Offline section-text extraction, with the extraction tool recorded.

ADR 0014 §6 extracted the recorded ss 55-56 text with `pdftotext -layout` from
**poppler-utils**. That detail is not cosmetic: Xpdf also ships a `pdftotext`,
the two implementations lay text out differently, and different text means a
different `text_sha256`. A sections file that does not say which tool produced
it cannot be reproduced, so `ExtractionTool` is recorded in every file this
module writes and `verified` is always `false` on the way out.

Nothing here reaches the network. `pdftotext` is invoked on a local staged file
through an injectable runner, so tests never shell out.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from scripts.wa_ingest.staging import compute_digest

MAX_EXTRACT_SECONDS: Final = 120
MAX_TEXT_CHARS: Final = 2_000_000

POPPLER: Final = "poppler-utils"
XPDF: Final = "xpdf"

_BLANK_RUN = re.compile(r"\n{3,}")
_VERSION_LINE = re.compile(r"pdftotext\s+version\s+(?P<version>[0-9][0-9.]*)", re.IGNORECASE)


class ExtractionError(Exception):
    """Extraction was refused or failed. Nothing was written."""


CommandRunner = Callable[[Sequence[str]], str]
"""Runs a command and returns its stdout. Injected so tests never shell out."""


def _default_runner(command: Sequence[str]) -> str:
    """Run an extraction command. A nonzero exit is a failure."""

    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell, local file only
        list(command),
        capture_output=True,
        text=True,
        timeout=MAX_EXTRACT_SECONDS,
        check=False,
    )
    if completed.returncode != 0:
        raise ExtractionError(
            f"pdftotext exited {completed.returncode}: {completed.stderr.strip()[:400]}"
        )
    return completed.stdout


def _default_probe(command: Sequence[str]) -> str:
    """Run a version probe, tolerating how each implementation reports itself.

    Xpdf prints its banner to stderr and exits 99; poppler prints to stderr and
    exits 0. Neither is an error, so the probe ignores the exit code and returns
    both streams. Extraction proper still demands exit 0 via `_default_runner`.
    """

    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell, no file input
        list(command),
        capture_output=True,
        text=True,
        timeout=MAX_EXTRACT_SECONDS,
        check=False,
    )
    return completed.stdout + "\n" + completed.stderr


@dataclass(frozen=True, slots=True)
class ExtractionTool:
    """Which `pdftotext` produced a sections file, and at what version."""

    implementation: str
    version: str

    def as_record(self) -> dict[str, str]:
        return {"implementation": self.implementation, "version": self.version}


def detect_tool(runner: CommandRunner | None = None) -> ExtractionTool:
    """Identify the local `pdftotext`, or refuse.

    Xpdf prints its own copyright line; poppler prints Poppler's. Guessing
    between them would silently change every digest this module produces, so an
    unrecognised banner is refused rather than assumed.
    """

    run = runner or _default_probe
    try:
        banner = run(["pdftotext", "-v"])
    except FileNotFoundError as exc:
        raise ExtractionError("pdftotext is not installed or not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ExtractionError("pdftotext -v timed out") from exc
    except ExtractionError:
        raise
    except OSError as exc:
        raise ExtractionError(f"pdftotext could not be run: {exc}") from exc

    lowered = banner.casefold()
    match = _VERSION_LINE.search(banner)
    if match is None:
        raise ExtractionError(f"unrecognised pdftotext banner: {banner.strip()[:200]!r}")
    version = match.group("version")

    if "poppler" in lowered:
        return ExtractionTool(implementation=POPPLER, version=version)
    if "glyph & cog" in lowered or "xpdfreader" in lowered or "xpdf" in lowered:
        return ExtractionTool(implementation=XPDF, version=version)
    raise ExtractionError(
        "pdftotext implementation could not be identified from its banner; "
        "record it explicitly rather than guessing"
    )


EXPECTED_IMPLEMENTATION: Final = POPPLER
"""The implementation ADR 0014 §6 used for the recorded ss 55-56 text.

Extracting a new source with a different implementation is allowed, but it must
be a decision someone made, not something that happened. `require_tool` is how
the operator states it.
"""


def require_tool(tool: ExtractionTool, *, expected: str = EXPECTED_IMPLEMENTATION) -> None:
    """Refuse unless the detected tool is the one the operator expected.

    The corpus already contains text produced by poppler. Producing the next
    source with Xpdf is not wrong, but it makes two instruments' digests
    non-comparable in provenance terms, so it has to be asked for explicitly.
    """

    if tool.implementation != expected:
        raise ExtractionError(
            f"extraction tool is {tool.implementation} {tool.version}, expected "
            f"{expected}. ADR 0014 §6 recorded the existing corpus with "
            f"{EXPECTED_IMPLEMENTATION}; extracting with a different "
            f"implementation changes the text and therefore every digest. "
            f"Pass --expect-tool {tool.implementation} to accept this deliberately."
        )


def normalise_extracted_text(raw: str) -> str:
    """Apply the ADR 0014 §6 normalisation, and nothing else.

    Line endings become LF, trailing whitespace is stripped per line, runs of
    blank lines collapse to one, and the result is stripped at both ends. No
    spelling, punctuation or content correction of any kind is applied: the text
    must remain the source's, not the tool's opinion of it.
    """

    if len(raw) > MAX_TEXT_CHARS:
        raise ExtractionError(f"extracted text exceeds {MAX_TEXT_CHARS} characters")
    unified = raw.replace("\r\n", "\n").replace("\r", "\n")
    stripped = "\n".join(line.rstrip() for line in unified.split("\n"))
    return _BLANK_RUN.sub("\n\n", stripped).strip()


def extract_page_range(
    *,
    pdf_path: Path,
    first_page: int,
    last_page: int,
    runner: CommandRunner | None = None,
) -> str:
    """Return normalised text for an inclusive page range of a staged file."""

    if first_page < 1 or last_page < first_page:
        raise ExtractionError(f"invalid page range: {first_page}-{last_page}")
    if not pdf_path.is_file():
        raise ExtractionError(f"no such staged file: {pdf_path}")
    run = runner or _default_runner
    raw = run(
        [
            "pdftotext",
            "-layout",
            "-f",
            str(first_page),
            "-l",
            str(last_page),
            str(pdf_path),
            "-",
        ]
    )
    return normalise_extracted_text(raw)


@dataclass(frozen=True, slots=True)
class SectionDraft:
    """One extracted section, before an operator has verified anything."""

    identifier: str
    heading: str | None
    text: str

    def __post_init__(self) -> None:
        if not self.identifier.strip():
            raise ExtractionError("section identifier must not be blank")
        if not self.text.strip():
            raise ExtractionError(f"section {self.identifier!r} extracted no text")


def build_sections_file(
    *,
    source_id: str,
    source_document_sha256: str,
    tool: ExtractionTool,
    drafts: Sequence[SectionDraft],
) -> dict[str, Any]:
    """Return the companion sections payload for a staged source.

    `verified` is written as `false` for every entry, unconditionally. This
    function has no parameter that could set it otherwise: flipping the flag is
    gate G2, a human act recorded separately, and nothing automated may do it.
    """

    if not drafts:
        raise ExtractionError("refusing to write a sections file with no sections")

    seen: set[str] = set()
    for draft in drafts:
        key = " ".join(draft.identifier.split()).casefold()
        if key in seen:
            raise ExtractionError(f"duplicate section identifier: {draft.identifier!r}")
        seen.add(key)

    return {
        "source_id": source_id,
        "source_document_sha256": source_document_sha256,
        "extraction": {
            "tool": tool.as_record(),
            "arguments": ["-layout"],
            "normalisation": (
                "line endings to LF; trailing whitespace stripped per line; runs of "
                "blank lines collapsed to one; leading and trailing blank lines removed"
            ),
        },
        "notes": [
            "Every section is unverified. `verified` becomes true only after an "
            "independent human has compared the text against the official source "
            "document, recorded under gate G2. No automated step may set it.",
            "Extraction output depends on the pdftotext implementation and version "
            "recorded above. Re-extracting with a different tool will produce "
            "different digests.",
        ],
        "sections": [
            {
                "identifier": draft.identifier,
                "heading": draft.heading,
                "text": draft.text,
                "text_sha256": section_text_digest(draft.text),
                "verified": False,
            }
            for draft in drafts
        ],
    }


def section_text_digest(text: str) -> str:
    """The ADR 0014 §3 convention, restated so tooling and runtime agree."""

    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_staged_digest(pdf_path: Path, expected: str) -> None:
    """Refuse unless a staged file still has the digest its manifest claims."""

    actual = compute_digest(pdf_path)
    if actual != expected:
        raise ExtractionError(
            f"staged file digest changed: manifest says {expected}, bytes give {actual}"
        )
