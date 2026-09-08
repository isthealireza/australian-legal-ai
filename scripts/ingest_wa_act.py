"""Record one WA Act end-to-end as a byte-exact, derived-provision fixture.

Operator tool, not product runtime. One command records one new Act:

    uv run --locked python scripts/ingest_wa_act.py \
        --root tests/fixtures/wa_legislation \
        --slug owner_drivers_contracts_and_disputes_act_2007 \
        --act-title "Owner-Drivers (Contracts and Disputes) Act 2007" \
        --act-number "007 of 2007" \
        --assent-date 2007-06-06 \
        --version-suffix 01-g0-00 \
        --currency-start 2025-01-31 \
        --status-date 2025-01-31 \
        --act-page-url \
            "https://www.legislation.wa.gov.au/legislation/statutes.nsf/"
            "law_a146614.html" \
        --pdf-url \
            "https://www.legislation.wa.gov.au/legislation/statutes.nsf/"
            "RedirectURL?OpenAgent&query=mrdoc_48249.pdf" \
        --sections "s 4,s 6,s 7"

The tool downloads the official consolidated PDF byte-exact, verifies the
text layer and (optionally) the caller-supplied digest, chooses the verbatim
heading of every requested section from the extracted text, and records only
the sections that actually exist there. All writes stay inside
`<root>/<slug>/`; the manifest records the real bytes, the real digest and
the real retrieval timestamp of the run.

Fail closed (recorded text is data, never instruction): a section that cannot
be located is DROPPED and reported as MISSING rather than invented; a digest
mismatch, a missing text layer, or an all-missing slice refuses the whole
run before anything is written.

The HTTP client is injectable so offline tests can serve recorded fixture
bytes through ``httpx.MockTransport``; the default is a real client that
follows the official redirect to the filestore.

Exit codes: 0 = every candidate confirmed; 1 = refusal (nothing written);
2 = some candidates dropped but at least one section was recorded.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import pypdf

from legal_ai.research.types import WA_ALLOWLISTED_HOSTS

# Running ``python scripts/ingest_wa_act.py`` puts only ``scripts/`` on
# sys.path, so the repo root must be added for ``scripts.derive_wa_provisions``.
_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from scripts.derive_wa_provisions import (  # noqa: E402
    _UNIT_START,
    DERIVATION_STEPS,
    NEWLINE,
    _extract,
    _is_noise,
    _section_number,
    _write,
)

_MIN_TEXT_CHARS = 1000
_SECTION = re.compile(r"^s\.?\s*\d+[A-Z]*$")
_SUFFIX = re.compile(r"^\d{2}-[a-z0-9]{1,2}-[a-z0-9]{2}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MRDOC = re.compile(r"mrdoc_\d+")
_TRAILING_PAGE_NUMBER = re.compile(r" \d+$")
_SLUG = re.compile(r"^[a-z0-9_]+$")
_NON_SECTION_LINE = re.compile(r"^\d+[A-Z]*\.\s+\S")

_TYPE_PREFIX = "wa_legislation:"
_ENCODING_NOTE = (
    "binary; application/pdf; stored byte-exact with no transformation, "
    "normalisation, re-serialisation, or correction"
)
_HASH_CONVENTION = (
    "SHA-256 computed over the exact stored file bytes; binary file, no "
    "trailing-newline convention applied"
)

#: Each element is (identifier, number, heading, body).
ConfirmedSections = list[tuple[str, str, str, str]]


class _Refusal(Exception):
    """A deterministic refusal that aborts the run before anything is written."""

    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record one WA Act fixture: byte-exact PDF + manifest + derived provisions."
    )
    parser.add_argument(
        "--root", required=True, help="fixture root (e.g. tests/fixtures/wa_legislation)"
    )
    parser.add_argument(
        "--slug", required=True, help="new fixture directory name, e.g. sale_of_goods_act_1895"
    )
    parser.add_argument("--act-title", required=True, help="official registry title of the Act")
    parser.add_argument(
        "--act-number", required=True, help="act number as recorded, e.g. '007 of 2007'"
    )
    parser.add_argument("--assent-date", required=True, help="assent date, YYYY-MM-DD")
    parser.add_argument(
        "--version-suffix", required=True, help="official consolidated suffix, e.g. 05-d0-06"
    )
    parser.add_argument(
        "--currency-start", required=True, help="version currency start, YYYY-MM-DD"
    )
    parser.add_argument("--status-date", required=True, help="recorded status date, YYYY-MM-DD")
    parser.add_argument(
        "--act-page-url",
        required=True,
        help="official act page URL, e.g. https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_a726.html",
    )
    parser.add_argument(
        "--pdf-url",
        required=True,
        help="official redirect URL, e.g. https://www.legislation.wa.gov.au/legislation/statutes.nsf/"
        "RedirectURL?OpenAgent&query=mrdoc_19856.pdf",
    )
    parser.add_argument(
        "--expected-sha256",
        default="",
        help="optional exact lowercase sha256 of the downloaded bytes; any mismatch "
        "refuses the run",
    )
    parser.add_argument(
        "--sections",
        required=True,
        help="comma-separated candidate sections in the form 's 8,s 9,s 10'",
    )
    return parser


def _parse_iso_date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise _Refusal(f"{label} must be a valid YYYY-MM-DD date (got {value!r})") from exc


def _url_refusal(value: str) -> str | None:
    """Return a reason string if the URL is not an allowlisted WA HTTPS URL."""

    if value != value.strip() or any(ord(character) < 32 for character in value):
        return "URL contains surrounding whitespace or control characters"
    try:
        parts = urlsplit(value)
        port = parts.port
        hostname = parts.hostname
    except ValueError:
        return "URL is malformed"
    if parts.scheme != "https":
        return "URL must use HTTPS"
    if (
        hostname not in WA_ALLOWLISTED_HOSTS
        or port not in (None, 443)
        or parts.username is not None
        or parts.password is not None
    ):
        return "URL host is not on the closed WA allowlist"
    return None


def _memory_lines(content: bytes) -> list[str]:
    """Return every content line of the downloaded bytes, furniture removed.

    Reuses the exact noise rules of ``scripts/derive_wa_provisions.py`` so the
    recorded provisions derive from the same deterministic document view.
    """

    reader = pypdf.PdfReader(io.BytesIO(content))
    lines: list[str] = []
    for page in reader.pages:
        for raw in (page.extract_text() or "").splitlines():
            line = raw.strip()
            if not _is_noise(line):
                lines.append(line)
    return lines


def _resolve_heading(lines: list[str], number: str, body: str) -> str | None:
    """Return the verbatim section heading from the official text layer.

    Every occurrence of ``<number>. `` in the document is a heading candidate
    (table-of-contents entries and body headings; sections whose body text
    does not start with a subsection marker rejoin their first lines). The
    heading is the shortest surviving candidate that is a prefix of the
    reflowed section body, which deterministically rules out unrelated
    scheduled clauses and page-number tails.
    """

    needle = re.compile(rf"^{re.escape(number)}\.\s+")
    body_head = body.splitlines()[0] if body else ""
    folded_body = re.sub(
        r"\s+", " ", re.sub(rf"^{re.escape(number)}\.\s+", "", body_head, count=1)
    ).strip()
    best: str | None = None
    for index, line in enumerate(lines):
        match = needle.match(line)
        if match is None:
            continue
        fragment = line[match.end() :].strip()
        cursor = index + 1
        while cursor < len(lines) and _UNIT_START.match(lines[cursor]) is None:
            fragment = f"{fragment} {lines[cursor]}".strip()
            cursor += 1
        fragment = _TRAILING_PAGE_NUMBER.sub("", fragment)
        folded = re.sub(r"\s+", " ", fragment).strip()
        if folded and folded_body.startswith(folded) and (best is None or len(folded) < len(best)):
            best = folded
    return best


def _sections_from_args(values: str) -> list[str]:
    raw = [part.strip() for part in values.split(",") if part.strip()]
    if not raw:
        raise _Refusal("--sections must list at least one section such as 's 8,s 9,s 10'")
    sections: list[str] = []
    for section in raw:
        if _SECTION.fullmatch(section) is None:
            raise _Refusal(
                f"unsupported provision identifier: {section!r} (expected the form 's 8' or 's 5A')"
            )
        sections.append(section)
    return sections


def _mrdoc_document_id(pdf_url: str) -> str:
    match = _MRDOC.search(pdf_url)
    if match is None:
        raise _Refusal("--pdf-url does not contain an official mrdoc_NNNNN document id")
    return match.group(0)


def _confirm_sections(
    lines: list[str], joined: str, sections: list[str]
) -> tuple[ConfirmedSections, list[str]]:
    confirmed: ConfirmedSections = []
    missing: list[str] = []
    for section in sections:
        number = _number_for(section)
        try:
            body = _extract(joined, number)
        except SystemExit:
            missing.append(section)
            print(f"MISSING {section}")
            continue
        heading = _resolve_heading(lines, number, body)
        if heading is None:
            missing.append(section)
            print(f"MISSING {section}")
            continue
        confirmed.append((section, number, heading, body))
    return confirmed, missing


def _number_for(section: str) -> str:
    """Return the section number, trusting ``_sections_from_args`` validation."""

    return _section_number(section)


def _section_list_note(confirmed: ConfirmedSections) -> str:
    headings = [identifier for identifier, _number, _heading, _body in confirmed]
    if len(headings) == 1:
        return headings[0]
    return ", ".join(headings[:-1]) + " and " + headings[-1]


def _readme(
    act_title: str,
    act_number: str,
    assent: date,
    suffix: str,
    document_id: str,
    currency_start: date,
    retrieved_at_utc: str,
    sha256: str,
    file_base: str,
    confirmed: ConfirmedSections,
) -> str:
    pinned = "\n".join(
        f'- **{identifier}** - "{heading}"' for identifier, _number, heading, _body in confirmed
    )
    sidecars = ", ".join(
        f"`provisions/{identifier.replace(' ', '_').replace('.', '')}[.txt\\|.provision.json]`"
        for identifier, _number, _heading, _body in confirmed
    )
    return f"""# WA Legislation Fixture - {act_title} (WA)

Recorded, durable, version-controlled test/evaluation fixture for the
Phase 4/5 research corpus.

## What this is

- One shared **whole-Act official consolidated PDF** of the {act_title}
  (WA), captured byte-exact from `legislation.wa.gov.au`.
- A paired manifest recording provenance, version/currency, status, retrieval
  timestamp, SHA-256, and the pinned provisions.
- Per-section text under `provisions/`, derived by
  `scripts/ingest_wa_act.py` from the recorded PDF.

## Files

| File | Purpose |
|---|---|
| `{file_base}.pdf` | Official consolidated PDF, byte-exact |
| `{file_base}.manifest.json` | Provenance + SHA-256 + pinpoints |
| {sidecars} | Derived section text + digests |

## Source and version

- **Act:** {act_title} (WA), Act No. {act_number}, assent {assent:%d %b %Y}.
- **Version:** Official consolidated version, suffix `{suffix}`, document
  `{document_id}`.
- **Currency:** start **{currency_start:%d %b %Y}**; end **Current** (in force
  at retrieval).
- **Retrieved (UTC):** `{retrieved_at_utc}`
- **SHA-256:** `{sha256}`

## Pinned provisions

{pinned}

## Limitations

- **Not a live legal-currency service.** This is a point-in-time snapshot for
  deterministic testing only and may not reflect amendments made after the
  retrieval timestamp.
- The recorded official URLs use host `www.legislation.wa.gov.au`, which is on
  the closed two-host allowlist of exactly `legislation.wa.gov.au` and
  `www.legislation.wa.gov.au` (HTTPS).
"""


def _run(args: argparse.Namespace, client: httpx.Client | None) -> int:
    root = Path(args.root).resolve()
    if not root.is_dir():
        raise _Refusal(f"fixture root does not exist or is not a directory: {root}")
    slug = str(args.slug).strip()
    if _SLUG.fullmatch(slug) is None:
        raise _Refusal(
            "--slug must be a plain lowercase directory name (letters, digits, underscores)"
        )
    target = root / slug
    if target.exists():
        raise _Refusal(
            f"fixture directory already exists: {target}; refusing to overwrite a recorded fixture "
            "(delete it explicitly to re-ingest)"
        )

    act_title = str(args.act_title).strip()
    act_number = str(args.act_number).strip()
    if not act_title or not act_number:
        raise _Refusal("--act-title and --act-number must not be blank")
    assent = _parse_iso_date(str(args.assent_date), "--assent-date")
    currency_start = _parse_iso_date(str(args.currency_start), "--currency-start")
    status_date = _parse_iso_date(str(args.status_date), "--status-date")

    suffix = str(args.version_suffix).strip()
    if _SUFFIX.fullmatch(suffix) is None:
        raise _Refusal(
            "--version-suffix must look like an official WA version suffix, e.g. '05-d0-06'"
        )

    sections = _sections_from_args(str(args.sections))

    act_page_url = str(args.act_page_url).strip()
    pdf_url = str(args.pdf_url).strip()
    for label, value in (("--act-page-url", act_page_url), ("--pdf-url", pdf_url)):
        reason = _url_refusal(value)
        if reason is not None:
            raise _Refusal(f"{label}: {reason}")
    official_source_url = (
        act_page_url
        if "&view=consolidated" in act_page_url
        else f"{act_page_url}&view=consolidated"
    )
    document_id = _mrdoc_document_id(pdf_url)

    expected = str(args.expected_sha256).strip()
    if expected and _SHA256.fullmatch(expected) is None:
        raise _Refusal("--expected-sha256 must be exactly 64 lowercase hexadecimal characters")

    actual_client = (
        client if client is not None else httpx.Client(follow_redirects=True, timeout=120.0)
    )
    try:
        response = actual_client.get(pdf_url)
    except httpx.HTTPError as exc:
        raise _Refusal(f"download failed: {exc}") from exc
    finally:
        if client is None:
            actual_client.close()

    if response.status_code != 200:
        raise _Refusal(f"unexpected HTTP status {response.status_code} from {pdf_url}")
    resolved_file_url = str(response.url)
    reason = _url_refusal(resolved_file_url)
    if reason is not None:
        raise _Refusal(f"resolved file URL: {reason}")

    content = response.content
    if not content.startswith(b"%PDF"):
        raise _Refusal("downloaded bytes do not start with the %PDF signature")
    byte_length = len(content)
    sha256 = hashlib.sha256(content).hexdigest()
    if expected and expected != sha256:
        raise _Refusal(
            f"digest mismatch: expected {expected} but the downloaded bytes hash to {sha256}"
        )
    content_type = response.headers.get("content-type", "application/pdf")
    retrieved_at_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"downloaded {pdf_url}")
    print(f"  resolved file url: {resolved_file_url}")
    print(f"  http {response.status_code} {content_type}; {byte_length} bytes; sha256 {sha256}")

    try:
        reader = pypdf.PdfReader(io.BytesIO(content))
        probe_chars = sum(len(page.extract_text() or "") for page in reader.pages)
    except Exception as exc:
        raise _Refusal(f"PDF text layer could not be read: {exc}") from exc
    if probe_chars < _MIN_TEXT_CHARS:
        raise _Refusal(
            f"PDF text layer is too small to be the consolidated Act "
            f"({probe_chars} characters); refusing"
        )
    print(f"  text layer: {probe_chars} characters")

    try:
        lines = _memory_lines(content)
    except Exception as exc:
        raise _Refusal(f"PDF text layer could not be read: {exc}") from exc
    joined = NEWLINE.join(lines)

    confirmed, missing = _confirm_sections(lines, joined, sections)
    if not confirmed:
        raise _Refusal(
            f"none of the requested sections could be located in the official text layer: "
            f"{', '.join(missing)}"
        )

    file_base = f"{slug}_consolidated_{suffix}"
    pdf_filename = f"{file_base}.pdf"
    manifest_name = f"{file_base}.manifest.json"
    source_id = f"{_TYPE_PREFIX}{slug}:consolidated:{suffix}"
    version_label = f"{act_title} - [{suffix}]"
    source_statement = f"Currency start {currency_start:%d %b %Y}; Currency end: Current (in force)"
    provisions = [
        {"identifier": identifier, "pinpoint": f"section {number}", "heading": heading}
        for identifier, number, heading, _body in confirmed
    ]
    manifest: dict[str, Any] = {
        "source_id": source_id,
        "source_system": "wa_legislation",
        "jurisdiction": "WA",
        "act": {
            "title": act_title,
            "jurisdiction": "WA",
            "act_number": act_number,
            "assent_date": f"{assent:%Y-%m-%d}",
        },
        "provisions": provisions,
        "version": {
            "type": "consolidated",
            "official_version": True,
            "suffix": suffix,
            "document_id": document_id,
            "version_label": version_label,
            "currency_start": f"{currency_start:%Y-%m-%d}",
            "currency_end": "current",
        },
        "status": {
            "in_force": True,
            "currency": "Current",
            "status_date": f"{status_date:%Y-%m-%d}",
            "source_statement": source_statement,
        },
        "request": {
            "method": "GET",
            "url": pdf_url,
            "resolved_file_url": resolved_file_url,
        },
        "official_source_url": official_source_url,
        "retrieved_at_utc": retrieved_at_utc,
        "http_status": response.status_code,
        "content_type": content_type,
        "content_length": byte_length,
        "file": pdf_filename,
        "sha256": sha256,
        "encoding": _ENCODING_NOTE,
        "hash_convention": _HASH_CONVENTION,
        "notes": [
            f"Whole-Act official consolidated PDF captured as a single shared fixture; "
            f"{_section_list_note(confirmed)} are recorded as pinpoints and derived to "
            "per-section text in the provisions/ subdirectory.",
            "Recorded fixtures are a point-in-time snapshot for deterministic testing only. "
            "They are NOT a live legal-currency service and may not reflect amendments made "
            "after the retrieval timestamp.",
            "Per-section exact-text extraction and deterministic validation are performed by "
            "scripts/ingest_wa_act.py (ADR 0013), using the scripts/derive_wa_provisions.py "
            "extraction logic.",
            "The official host is www.legislation.wa.gov.au, a subdomain of legislation.wa.gov.au.",
        ],
    }

    target.mkdir(parents=True, exist_ok=False)
    provisions_dir = target / "provisions"
    provisions_dir.mkdir(exist_ok=True)
    with target.joinpath(manifest_name).open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2)

    derived_at_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    for identifier, number, heading, body in confirmed:
        record: dict[str, Any] = {
            "parent_source_id": source_id,
            "parent_sha256": sha256,
            "jurisdiction": "WA",
            "act_title": act_title,
            "provision_identifier": identifier,
            "pinpoint": f"section {number}",
            "heading": heading,
            "source_version": suffix,
            "official_source_url": official_source_url,
            "derived_at_utc": derived_at_utc,
            "derivation": {
                "tool": "scripts/ingest_wa_act.py",
                "steps": list(DERIVATION_STEPS),
            },
            "notes": [
                "Derived text, not official bytes. The official source is the parent PDF.",
                "Quotes are validated against this file's recorded digest.",
            ],
        }
        written = _write(provisions_dir, identifier, body, record)
        assert record["parent_sha256"] == manifest["sha256"]
        assert (
            record["sha256"]
            == hashlib.sha256((provisions_dir / record["file"]).read_bytes()).hexdigest()
        )
        print(f"  provision {identifier}: {record['byte_length']} bytes -> {written.name}")

    target.joinpath(pdf_filename).write_bytes(content)
    target.joinpath("README.md").write_text(
        _readme(
            act_title,
            act_number,
            assent,
            suffix,
            document_id,
            currency_start,
            retrieved_at_utc,
            sha256,
            file_base,
            confirmed,
        ),
        encoding="utf-8",
        newline="\n",
    )

    print(f"INGESTED {act_title} [{suffix}] -> {target}")
    print(f"  file: {pdf_filename} ({byte_length} bytes; sha256 {sha256})")
    print(f"  manifest: {manifest_name}")
    for identifier, _number, heading, body in confirmed:
        print(f"  {identifier}: {heading} ({len(body)} chars)")
    if missing:
        print(f"NOT RECORDED (missing from the official text layer): {', '.join(missing)}")
        return 2
    return 0


def main(argv: list[str] | None = None, *, client: httpx.Client | None = None) -> int:
    """Run ingestion for one Act, returning the exit code and never raising."""
    args = _parser().parse_args(argv)
    try:
        return _run(args, client)
    except _Refusal as exc:
        print(f"REFUSED: {exc}")
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
