# Corpus-Expansion WA Slice — Dependency Baseline Snapshot

`scripts/ingest_wa_act.py` imports two pre-existing, UNCHANGED modules. Those
modules are committed on the base ref (`84e4ddc`) and are therefore not part of
this task's diff; the external review gate cannot see them in the bundle. This
file snapshots the exact, committed definitions verbatim so a reviewer can
confirm the host allowlist and the derivation internals that the ingestion
script relies on.

Both modules are already recorded as reviewed: `legal_ai.research.types`
(pure constants, ADR 0013 §3) and `scripts/derive_wa_provisions.py` (operator
tool delivered and gate-PASSed under the Phase 5 task, ADR 0015). Neither is
modified by this task.

## 1. `legal_ai.research.types.WA_ALLOWLISTED_HOSTS` (verbatim, committed at 84e4ddc)

```python
WA_SOURCE_SYSTEM: Final = "wa_legislation"
WA_JURISDICTION: Final = "WA"

#: Closed, exact HTTPS hostname allowlist from ADR 0013 §3. No wildcard
#: subdomain is trusted and no other host is permitted.
WA_ALLOWLISTED_HOSTS: Final = frozenset(
    {
        "legislation.wa.gov.au",
        "www.legislation.wa.gov.au",
    }
)
```

`ingest_wa_act.py` imports `WA_ALLOWLISTED_HOSTS` and refuses any URL whose
host is not in this closed two-host set. The set is `frozenset`, so it cannot
be widened at runtime by the ingestion script.

## 2. `scripts/derive_wa_provisions.py` internals imported by `ingest_wa_act.py` (verbatim, committed at 84e4ddc)

The ingestion script reuses these exact names; it does not reimplement them.

```python
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
    """Join layout-wrapped lines so each structural unit is one line. ..."""

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
    """Return the exact text of one section, from its heading to the next. ..."""

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
```

Note: the ellipses (`...`) inside the docstrings above are the original
docstrings' continuation text, abbreviated here only for width. The code is
otherwise verbatim and unmodified by this task.