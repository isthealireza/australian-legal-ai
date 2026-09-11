"""Deterministic staging and manifest generation.

Every function here is pure with respect to the network and the clock. Digests
are recomputed from bytes on disk, never copied from an input, and the manifest
is serialised with sorted keys so the same inputs always produce byte-identical
output.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Final

MAX_SOURCE_BYTES: Final = 64 * 1024 * 1024
"""A whole consolidated instrument is large but bounded. Anything past this is
not a legislative PDF and is refused rather than staged."""

WA_ALLOWLISTED_HOSTS: Final = frozenset({"legislation.wa.gov.au", "www.legislation.wa.gov.au"})
"""Mirrors `legal_ai.research.types.WA_ALLOWLISTED_HOSTS`. Duplicated on
purpose: operator tooling must not import the product package, and a staged
manifest that would fail the runtime allowlist should fail here first."""

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_VERSION_SUFFIX = re.compile(r"^[0-9]{2}-[a-z]+[0-9]-[0-9]{2}$")


class StagingError(Exception):
    """Staging input was rejected. Nothing was written."""


def compute_digest(path: Path) -> str:
    """Return the SHA-256 of a file's exact bytes, read in bounded chunks."""

    size = path.stat().st_size
    if size > MAX_SOURCE_BYTES:
        raise StagingError(f"source exceeds {MAX_SOURCE_BYTES} bytes: {size}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slug_for_title(title: str) -> str:
    """Return the corpus directory slug for an Act title.

    Matches the existing corpus convention: `Road Traffic Act 1974` becomes
    `road_traffic_act_1974`. Parentheses and punctuation collapse to a single
    underscore, so `Road Traffic (Vehicles) Act 2012` becomes
    `road_traffic_vehicles_act_2012`.
    """

    collapsed = _SLUG_STRIP.sub("_", title.strip().casefold()).strip("_")
    if not collapsed:
        raise StagingError(f"title produces an empty slug: {title!r}")
    return collapsed


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    """The metadata an operator verified page-side before staging.

    Every field is supplied by the operator from the official source page. None
    is inferred, and none is fetched: this dataclass is the boundary where human
    verification enters the pipeline.
    """

    act_title: str
    act_number: str
    version_suffix: str
    currency_start: date
    status_currency: str
    status_in_force: bool
    status_date: date
    official_source_url: str
    retrieved_at: datetime
    version_type: str = "consolidated"
    assent_date: date | None = None
    currency_end: str | None = None

    def __post_init__(self) -> None:
        if not self.act_title.strip():
            raise StagingError("act_title must not be blank")
        if not _VERSION_SUFFIX.match(self.version_suffix):
            raise StagingError(
                f"version_suffix is not a WALW version code: {self.version_suffix!r}"
            )
        if self.retrieved_at.tzinfo is None or self.retrieved_at.utcoffset() != UTC.utcoffset(
            self.retrieved_at
        ):
            raise StagingError("retrieved_at must be an aware UTC instant")
        if self.status_date > self.retrieved_at.date():
            raise StagingError("status_date is later than the retrieval timestamp")
        if self.currency_start > self.status_date:
            raise StagingError("currency_start is later than status_date")
        if self.assent_date is not None and self.assent_date > self.currency_start:
            raise StagingError("assent_date is later than currency_start")
        _check_official_url(self.official_source_url)

    @property
    def slug(self) -> str:
        return slug_for_title(self.act_title)

    @property
    def source_id(self) -> str:
        return f"wa_legislation:{self.slug}:{self.version_type}:{self.version_suffix}"

    @property
    def stem(self) -> str:
        return f"{self.slug}_{self.version_type}_{self.version_suffix}"


def _check_official_url(url: str) -> None:
    """Refuse anything the runtime allowlist would later refuse."""

    from urllib.parse import urlsplit

    if url != url.strip() or any(ord(character) < 32 for character in url):
        raise StagingError("official_source_url contains control characters or padding")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise StagingError(f"official_source_url is unparseable: {exc}") from exc
    if parsed.scheme != "https":
        raise StagingError("official_source_url must be https")
    if parsed.hostname not in WA_ALLOWLISTED_HOSTS:
        raise StagingError(f"host is not an allowlisted WALW host: {parsed.hostname!r}")
    if port not in (None, 443):
        raise StagingError("official_source_url must use the default https port")
    if parsed.username is not None or parsed.password is not None:
        raise StagingError("official_source_url must not carry credentials")


@dataclass(frozen=True, slots=True)
class StagingLayout:
    """Where a staged source lives before promotion."""

    root: Path
    identity: SourceIdentity

    @property
    def directory(self) -> Path:
        return self.root / self.identity.slug / self.identity.version_suffix

    @property
    def pdf_path(self) -> Path:
        return self.directory / f"{self.identity.stem}.pdf"

    @property
    def manifest_path(self) -> Path:
        return self.directory / f"{self.identity.stem}.manifest.json"

    @property
    def sections_path(self) -> Path:
        return self.directory / f"{self.identity.stem}.sections.json"

    @property
    def approval_path(self) -> Path:
        return self.directory / "OWNER_APPROVAL.json"


def build_manifest(
    *,
    identity: SourceIdentity,
    pdf_path: Path,
    content_type: str = "application/pdf",
) -> dict[str, Any]:
    """Return the manifest for a staged source.

    The digest and byte length are recomputed from the file on disk. Neither is
    accepted as an input, so a manifest cannot claim a digest its own bytes do
    not have.
    """

    digest = compute_digest(pdf_path)
    act: dict[str, Any] = {
        "title": identity.act_title,
        "jurisdiction": "WA",
        "act_number": identity.act_number,
    }
    if identity.assent_date is not None:
        act["assent_date"] = identity.assent_date.isoformat()

    version: dict[str, Any] = {
        "type": identity.version_type,
        "official_version": True,
        "suffix": identity.version_suffix,
        "currency_start": identity.currency_start.isoformat(),
    }
    if identity.currency_end is not None:
        version["currency_end"] = identity.currency_end

    return {
        "source_id": identity.source_id,
        "source_system": "wa_legislation",
        "jurisdiction": "WA",
        "act": act,
        "provisions": [],
        "version": version,
        "status": {
            "in_force": identity.status_in_force,
            "currency": identity.status_currency,
            "status_date": identity.status_date.isoformat(),
        },
        "official_source_url": identity.official_source_url,
        "retrieved_at_utc": identity.retrieved_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "content_type": content_type,
        "content_length": pdf_path.stat().st_size,
        "file": pdf_path.name,
        "sha256": digest,
        "encoding": (
            "binary; application/pdf; stored byte-exact with no transformation, "
            "normalisation, re-serialisation, or correction"
        ),
        "hash_convention": (
            "SHA-256 computed over the exact stored file bytes; binary file, no "
            "trailing-newline convention applied"
        ),
        "notes": [
            "Recorded fixtures are a point-in-time snapshot for deterministic "
            "testing only. They are NOT a live legal-currency service and may not "
            "reflect amendments made after the retrieval timestamp.",
            "Provisions are added by an operator after page-side verification; an "
            "empty list means none has been declared yet.",
        ],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON deterministically: sorted keys, two-space indent, LF, no BOM."""

    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def stage_source(
    *,
    identity: SourceIdentity,
    downloaded_pdf: Path,
    staging_root: Path,
) -> StagingLayout:
    """Copy an already-downloaded official file into the staging tree.

    This function does not fetch anything. `downloaded_pdf` is a file the
    operator obtained from the official source themselves, which is what keeps
    every network capability out of this repository.
    """

    if not downloaded_pdf.is_file():
        raise StagingError(f"no such file: {downloaded_pdf}")
    layout = StagingLayout(root=staging_root, identity=identity)
    if layout.pdf_path.exists():
        raise StagingError(f"already staged, refusing to overwrite: {layout.pdf_path}")
    layout.directory.mkdir(parents=True, exist_ok=True)
    layout.pdf_path.write_bytes(downloaded_pdf.read_bytes())
    write_json(layout.manifest_path, build_manifest(identity=identity, pdf_path=layout.pdf_path))
    return layout
