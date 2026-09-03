"""Derive per-provision text fixtures from a hash-verified WA source PDF.

This is an operator tool, not product runtime. It is run by a human, writes
only inside the fixture directory it is pointed at, and performs no network
access. The product's answering model never invokes it.

Provenance chain, enforced rather than asserted:

    official PDF bytes (sha256 recorded in the source manifest)
      -> this script verifies that digest before reading anything
      -> extracted provision text, written byte-exact
      -> provision manifest recording the parent digest and its own digest

`answering/provisions.py` refuses any provision whose recorded parent digest
does not equal the digest of the evidence packet in hand, so a derived text can
never be attached to a source it was not derived from.

Usage:

    uv run --locked python scripts/derive_wa_provisions.py \
        tests/fixtures/wa_legislation/road_traffic_act_1974
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pypdf

NEWLINE = "\n"

#: Repeated page furniture in the official WA consolidated layout. Removing it
#: and reflowing the remainder are the only transformations applied, and both
#: are recorded in every manifest.
_NOISE = (
    re.compile(r"^[A-Z][A-Za-z ]+ Act \d{4}$"),
    re.compile(r"^As at \d{1,2} \w+ \d{4} Official Version page .*$"),
    re.compile(r"^(page )?\d+ Official Version As at \d{1,2} \w+ \d{4}$"),
    re.compile(r"^\[PCO [^\]]+\] Published on www\.legislation\.wa\.gov\.au$"),
    re.compile(r"^Published on www\.legislation\.wa\.gov\.au \[PCO [^\]]+\]$"),
    re.compile(r"^s\. \d+[A-Z]*$"),
    re.compile(r"^(Part|Division|Subdivision) .*$"),
    re.compile(r"^.{0,60} (Part|Division|Subdivision) [IVXLC0-9]+[A-Z]?$"),
)

#: A line that begins a new structural unit rather than continuing the previous
#: one: a section heading, a subsection or paragraph marker, a penalty or note
#: line, or an amendment history note.
_UNIT_START = re.compile(r"^(?:\d+[A-Z]*\.\s|\(\w{1,4}\)\s|\[|Penalty|Penalties|Note)")

DERIVATION_STEPS = (
    "pypdf text extraction, page by page, in document order",
    "removal of repeated page headers, footers, and running Part/Division titles",
    "per-line whitespace trimming and removal of blank lines",
    "provision boundary detection between one section heading and the next",
    "reflow of layout-wrapped lines into one line per structural unit",
)


def _is_noise(line: str) -> bool:
    return not line or any(pattern.match(line) for pattern in _NOISE)


def _document_lines(pdf_path: Path) -> list[str]:
    """Return every content line of the document with page furniture removed."""

    reader = pypdf.PdfReader(str(pdf_path))
    lines: list[str] = []
    for page in reader.pages:
        for raw in (page.extract_text() or "").splitlines():
            line = raw.strip()
            if not _is_noise(line):
                lines.append(line)
    return lines


def _reflow(lines: list[str]) -> str:
    """Join layout-wrapped lines so each structural unit is one line.

    A consolidated PDF wraps text to the page width, so one subsection arrives
    as several lines broken mid-sentence. Those breaks are page furniture, not
    part of the provision. Leaving them in would mean no ordinary quotation of
    the provision could ever match the stored text byte-for-byte, which would
    make quote validation refuse every otherwise-correct answer.
    """

    units: list[str] = []
    for line in lines:
        if not units or _UNIT_START.match(line):
            units.append(line)
        else:
            units[-1] = f"{units[-1]} {line}"
    return NEWLINE.join(" ".join(unit.split()) for unit in units)


def _section_number(identifier: str) -> str:
    """Return the bare section number from an identifier such as 's 55'."""

    match = re.fullmatch(r"s\.?\s*(\d+[A-Z]*)", identifier.strip())
    if match is None:
        raise SystemExit(f"unsupported provision identifier: {identifier!r}")
    return match.group(1)


def _extract(joined: str, number: str) -> str:
    """Return the exact text of one section, from its heading to the next.

    A consolidated Act lists every section twice: once in the table of contents
    and once in the body. The table-of-contents entry is a heading with no
    substantive text, so the longest candidate is the body and the choice is
    deterministic rather than positional.
    """

    pattern = re.compile(
        rf"^{re.escape(number)}\.\s+.*?(?=^\d+[A-Z]*\.\s+\S)",
        re.MULTILINE | re.DOTALL,
    )
    candidates = [match.group(0).strip() for match in pattern.finditer(joined)]
    if not candidates:
        raise SystemExit(f"section {number} could not be located in the source")
    return _reflow(max(candidates, key=len).splitlines())


def _write(directory: Path, identifier: str, text: str, record: dict[str, Any]) -> Path:
    """Write the provision text and its manifest, recording both digests."""

    slug = identifier.replace(" ", "_").replace(".", "")
    text_path = directory / f"{slug}.txt"
    text_path.write_bytes(text.encode("utf-8"))
    record["file"] = text_path.name
    record["sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    record["byte_length"] = len(text.encode("utf-8"))
    manifest_path = directory / f"{slug}.provision.json"
    manifest_path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + NEWLINE, encoding="utf-8"
    )
    return manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Derive WA provision text fixtures.")
    parser.add_argument("fixture_dir", type=Path, help="directory holding the source manifest")
    args = parser.parse_args(argv)

    directory: Path = args.fixture_dir.resolve()
    manifests = sorted(directory.glob("*.manifest.json"))
    if len(manifests) != 1:
        raise SystemExit(f"expected exactly one source manifest in {directory}")
    source = json.loads(manifests[0].read_text(encoding="utf-8"))

    # The manifest is recorded data, so its filename is not trusted to stay
    # inside the fixture directory.
    filename = str(source["file"])
    if not filename.strip() or Path(filename).name != filename:
        raise SystemExit("recorded content filename must be a plain basename")
    pdf_path = (directory / filename).resolve()
    if not pdf_path.is_relative_to(directory) or pdf_path.is_symlink():
        raise SystemExit("recorded content file must be a regular file inside the fixture root")
    actual = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    if actual != source["sha256"]:
        raise SystemExit("parent source digest does not match its manifest; refusing to derive")
    print(f"parent digest verified: {actual}")

    provisions_dir = directory / "provisions"
    provisions_dir.mkdir(exist_ok=True)
    joined = NEWLINE.join(_document_lines(pdf_path))

    for provision in source["provisions"]:
        identifier = str(provision["identifier"])
        text = _extract(joined, _section_number(identifier))
        record: dict[str, Any] = {
            "parent_source_id": source["source_id"],
            "parent_sha256": source["sha256"],
            "jurisdiction": source["jurisdiction"],
            "act_title": source["act"]["title"],
            "provision_identifier": identifier,
            "pinpoint": provision["pinpoint"],
            "heading": provision.get("heading"),
            "source_version": source["version"]["suffix"],
            "official_source_url": source["official_source_url"],
            "derived_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "derivation": {
                "tool": "scripts/derive_wa_provisions.py",
                "steps": list(DERIVATION_STEPS),
            },
            "notes": [
                "Derived text, not official bytes. The official source is the parent PDF.",
                "Quotes are validated against this file's recorded digest.",
            ],
        }
        path = _write(provisions_dir, identifier, text, record)
        print(f"  {identifier}: {record['byte_length']} bytes -> {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
