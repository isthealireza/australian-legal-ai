"""Staging and manifest generation are deterministic and refuse bad input.

Every fixture here is synthetic. No test reads the recorded corpus, downloads
anything, or invokes an external tool.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from scripts.wa_ingest.staging import (
    SourceIdentity,
    StagingError,
    StagingLayout,
    build_manifest,
    compute_digest,
    slug_for_title,
    stage_source,
    write_json,
)

_CONTENT = b"%PDF-1.7 synthetic staging fixture"
_URL = "https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_s1.html"


def identity(**overrides: Any) -> SourceIdentity:
    fields: dict[str, Any] = {
        "act_title": "Synthetic Vehicles Act 2012",
        "act_number": "007 of 2012",
        "version_suffix": "01-j0-00",
        "currency_start": date(2024, 10, 7),
        "status_currency": "Current",
        "status_in_force": True,
        "status_date": date(2025, 1, 10),
        "official_source_url": _URL,
        "retrieved_at": datetime(2026, 8, 11, 10, 27, 3, tzinfo=UTC),
    }
    fields.update(overrides)
    return SourceIdentity(**fields)


def staged_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "downloaded.pdf"
    path.write_bytes(_CONTENT)
    return path


# ---------------------------------------------------------------------------
# Slugs and identity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "slug"),
    [
        ("Road Traffic Act 1974", "road_traffic_act_1974"),
        ("Road Traffic (Vehicles) Act 2012", "road_traffic_vehicles_act_2012"),
        ("Road Traffic (Administration) Act 2008", "road_traffic_administration_act_2008"),
        ("  Spaced   Title  2000 ", "spaced_title_2000"),
    ],
)
def test_slug_matches_the_corpus_convention(title: str, slug: str) -> None:
    assert slug_for_title(title) == slug


def test_a_title_with_no_alphanumerics_is_refused() -> None:
    with pytest.raises(StagingError):
        slug_for_title("()  --  ()")


def test_source_id_is_derived_not_supplied() -> None:
    assert identity().source_id == (
        "wa_legislation:synthetic_vehicles_act_2012:consolidated:01-j0-00"
    )


@pytest.mark.parametrize("suffix", ["14-t0-00", "01-j0-00", "05-aa0-00"])
def test_real_walw_version_codes_are_accepted(suffix: str) -> None:
    assert identity(version_suffix=suffix).version_suffix == suffix


@pytest.mark.parametrize("suffix", ["", "latest", "1-a-0", "01_j0_00", "01-j0-000000"])
def test_a_non_walw_version_code_is_refused(suffix: str) -> None:
    with pytest.raises(StagingError):
        identity(version_suffix=suffix)


def test_a_naive_retrieval_timestamp_is_refused() -> None:
    with pytest.raises(StagingError):
        identity(retrieved_at=datetime(2026, 8, 11, 10, 27, 3))


def test_a_status_date_after_retrieval_is_refused() -> None:
    with pytest.raises(StagingError):
        identity(status_date=date(2027, 1, 1))


def test_currency_start_after_status_date_is_refused() -> None:
    with pytest.raises(StagingError):
        identity(currency_start=date(2026, 1, 1), status_date=date(2025, 1, 10))


def test_assent_after_currency_start_is_refused() -> None:
    with pytest.raises(StagingError):
        identity(assent_date=date(2025, 6, 1))


@pytest.mark.parametrize(
    "url",
    [
        "http://www.legislation.wa.gov.au/x.html",
        "https://legislation.nsw.gov.au/x.html",
        "https://evil.example/legislation.wa.gov.au",
        "https://user:pw@www.legislation.wa.gov.au/x.html",
        "https://www.legislation.wa.gov.au:8443/x.html",
        " https://www.legislation.wa.gov.au/x.html",
    ],
)
def test_a_url_the_runtime_would_refuse_is_refused_at_staging(url: str) -> None:
    """Fail here rather than after the bytes are in the corpus."""

    with pytest.raises(StagingError):
        identity(official_source_url=url)


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def test_digest_and_length_come_from_the_bytes(tmp_path: Path) -> None:
    pdf = staged_pdf(tmp_path)
    manifest = build_manifest(identity=identity(), pdf_path=pdf)
    assert manifest["sha256"] == hashlib.sha256(_CONTENT).hexdigest()
    assert manifest["content_length"] == len(_CONTENT)


def test_manifest_shape_matches_the_recorded_corpus(tmp_path: Path) -> None:
    manifest = build_manifest(
        identity=identity(assent_date=date(2012, 5, 21)),
        pdf_path=staged_pdf(tmp_path),
    )
    assert manifest["source_system"] == "wa_legislation"
    assert manifest["jurisdiction"] == "WA"
    assert manifest["act"]["jurisdiction"] == "WA"
    assert manifest["act"]["act_number"] == "007 of 2012"
    assert manifest["act"]["assent_date"] == "2012-05-21"
    assert manifest["version"]["suffix"] == "01-j0-00"
    assert manifest["version"]["currency_start"] == "2024-10-07"
    assert manifest["status"] == {
        "in_force": True,
        "currency": "Current",
        "status_date": "2025-01-10",
    }
    assert manifest["retrieved_at_utc"] == "2026-08-11T10:27:03Z"


def test_provisions_start_empty_so_a_human_must_declare_them(tmp_path: Path) -> None:
    assert build_manifest(identity=identity(), pdf_path=staged_pdf(tmp_path))["provisions"] == []


def test_manifest_serialisation_is_byte_identical_across_runs(tmp_path: Path) -> None:
    pdf = staged_pdf(tmp_path)
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    write_json(first, build_manifest(identity=identity(), pdf_path=pdf))
    write_json(second, build_manifest(identity=identity(), pdf_path=pdf))
    assert first.read_bytes() == second.read_bytes()


def test_written_manifest_is_valid_json_with_sorted_keys(tmp_path: Path) -> None:
    path = tmp_path / "m.json"
    write_json(path, build_manifest(identity=identity(), pdf_path=staged_pdf(tmp_path)))
    text = path.read_text(encoding="utf-8")
    parsed = json.loads(text)
    assert list(parsed) == sorted(parsed)
    assert text.endswith("\n")
    assert "\r" not in text


# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------


def test_staging_writes_into_a_version_scoped_directory(tmp_path: Path) -> None:
    layout = stage_source(
        identity=identity(),
        downloaded_pdf=staged_pdf(tmp_path),
        staging_root=tmp_path / "staging",
    )
    assert layout.pdf_path.is_file()
    assert layout.manifest_path.is_file()
    assert layout.pdf_path.parent.name == "01-j0-00"
    assert layout.pdf_path.parent.parent.name == "synthetic_vehicles_act_2012"


def test_staging_never_touches_the_active_corpus(tmp_path: Path) -> None:
    active = tmp_path / "active"
    active.mkdir()
    stage_source(
        identity=identity(),
        downloaded_pdf=staged_pdf(tmp_path),
        staging_root=tmp_path / "staging",
    )
    assert list(active.iterdir()) == []


def test_staged_bytes_are_byte_exact(tmp_path: Path) -> None:
    layout = stage_source(
        identity=identity(),
        downloaded_pdf=staged_pdf(tmp_path),
        staging_root=tmp_path / "staging",
    )
    assert layout.pdf_path.read_bytes() == _CONTENT
    assert compute_digest(layout.pdf_path) == hashlib.sha256(_CONTENT).hexdigest()


def test_restaging_refuses_rather_than_overwriting(tmp_path: Path) -> None:
    kwargs = {
        "identity": identity(),
        "downloaded_pdf": staged_pdf(tmp_path),
        "staging_root": tmp_path / "staging",
    }
    stage_source(**kwargs)  # type: ignore[arg-type]
    with pytest.raises(StagingError):
        stage_source(**kwargs)  # type: ignore[arg-type]


def test_a_missing_download_is_refused(tmp_path: Path) -> None:
    with pytest.raises(StagingError):
        stage_source(
            identity=identity(),
            downloaded_pdf=tmp_path / "absent.pdf",
            staging_root=tmp_path / "staging",
        )


def test_layout_paths_are_all_inside_the_staging_root(tmp_path: Path) -> None:
    layout = StagingLayout(root=tmp_path / "staging", identity=identity())
    for path in (
        layout.pdf_path,
        layout.manifest_path,
        layout.sections_path,
        layout.approval_path,
    ):
        assert path.is_relative_to(tmp_path / "staging")
