"""Unit tests for deterministic recorded-fixture loading and selection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from legal_ai.research.corpus import RecordedWaCorpus
from legal_ai.research.errors import AmbiguousSelection, RecordedCorpusError
from tests.research.conftest import (
    RECORDED_ACT_TITLE,
    RECORDED_FIXTURE_ROOT,
    RECORDED_SHA256,
    RECORDED_SOURCE_ID,
    recorded_query,
)

_CONTENT = b"synthetic recorded content"


def _manifest(**overrides: Any) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "source_id": "wa_legislation:synthetic:consolidated:1-a0-00",
        "source_system": "wa_legislation",
        "jurisdiction": "WA",
        "act": {"title": "Synthetic Act 1974", "jurisdiction": "WA", "act_number": "001 of 1974"},
        "provisions": [{"identifier": "s 55", "pinpoint": "section 55", "heading": "Heading"}],
        "version": {"suffix": "1-a0-00", "currency_start": "2025-01-10"},
        "status": {"currency": "Current", "in_force": True, "status_date": "2025-01-10"},
        "official_source_url": "https://www.legislation.wa.gov.au/law_s1.html",
        "retrieved_at_utc": "2026-08-11T10:27:03Z",
        "sha256": hashlib.sha256(_CONTENT).hexdigest(),
        "file": "synthetic.pdf",
    }
    manifest.update(overrides)
    return manifest


def _write_corpus(root: Path, name: str = "synthetic", **overrides: Any) -> Path:
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "synthetic.pdf").write_bytes(_CONTENT)
    (directory / f"{name}.manifest.json").write_text(
        json.dumps(_manifest(**overrides)), encoding="utf-8"
    )
    return root


def test_recorded_fixture_is_selected_with_its_exact_recorded_metadata() -> None:
    corpus = RecordedWaCorpus(RECORDED_FIXTURE_ROOT)

    source = corpus.select(recorded_query())

    assert source is not None
    assert source.source_id == RECORDED_SOURCE_ID
    assert source.source_system == "wa_legislation"
    assert source.jurisdiction == "WA"
    assert source.act_title == RECORDED_ACT_TITLE
    assert source.act_jurisdiction == "WA"
    assert source.source_version == "14-t0-00"
    assert source.compilation_date == "2025-01-10"
    assert source.status_currency == "Current"
    assert source.status_in_force is True
    assert source.status_date == "2025-01-10"
    assert source.retrieved_at == "2026-08-11T10:27:03Z"
    assert source.sha256 == RECORDED_SHA256
    assert [provision.identifier for provision in source.provisions] == ["s 55", "s 56"]
    assert [provision.pinpoint for provision in source.provisions] == ["section 55", "section 56"]


def test_recorded_fixture_content_is_the_exact_unmodified_bytes() -> None:
    corpus = RecordedWaCorpus(RECORDED_FIXTURE_ROOT)

    source = corpus.select(recorded_query())

    assert source is not None
    on_disk = (
        RECORDED_FIXTURE_ROOT
        / "road_traffic_act_1974"
        / "road_traffic_act_1974_consolidated_14-t0-00.pdf"
    ).read_bytes()
    assert source.source_content == on_disk
    assert hashlib.sha256(source.source_content).hexdigest() == RECORDED_SHA256


def test_selection_is_deterministic_across_repeated_calls() -> None:
    corpus = RecordedWaCorpus(RECORDED_FIXTURE_ROOT)

    first = corpus.select(recorded_query())
    second = corpus.select(recorded_query())

    assert first == second


@pytest.mark.parametrize(
    "act_title",
    ["Sale of Goods Act 1895", "Fair Trading Act 2010", "Road Transport Act 2013"],
)
def test_out_of_corpus_acts_select_nothing(act_title: str) -> None:
    corpus = RecordedWaCorpus(RECORDED_FIXTURE_ROOT)

    assert corpus.select(recorded_query(act_title=act_title)) is None


def test_selection_matches_the_recorded_act_title_case_insensitively(tmp_path: Path) -> None:
    corpus = RecordedWaCorpus(_write_corpus(tmp_path))

    assert corpus.select(recorded_query(act_title="synthetic   act 1974")) is not None


def test_non_unique_recorded_sources_raise_rather_than_guess(tmp_path: Path) -> None:
    _write_corpus(tmp_path, "first")
    _write_corpus(tmp_path, "second")
    corpus = RecordedWaCorpus(tmp_path)

    with pytest.raises(AmbiguousSelection):
        corpus.select(recorded_query(act_title="Synthetic Act 1974"))


@pytest.mark.parametrize(
    "filename",
    [
        "../escape.pdf",
        "../../escape.pdf",
        "nested/synthetic.pdf",
        "nested\\synthetic.pdf",
        "  ",
        "..",
    ],
)
def test_manifest_declared_paths_cannot_leave_the_fixture_root(
    tmp_path: Path, filename: str
) -> None:
    (tmp_path / "escape.pdf").write_bytes(b"outside content")
    corpus_root = tmp_path / "corpus"
    _write_corpus(corpus_root, file=filename)

    with pytest.raises(RecordedCorpusError):
        RecordedWaCorpus(corpus_root)


def test_missing_content_file_refuses_to_load(tmp_path: Path) -> None:
    _write_corpus(tmp_path, file="absent.pdf")

    with pytest.raises(RecordedCorpusError):
        RecordedWaCorpus(tmp_path)


@pytest.mark.parametrize("body", ["not json", "[]", '"a string"', "123"])
def test_structurally_unusable_manifests_refuse_to_load(tmp_path: Path, body: str) -> None:
    directory = tmp_path / "broken"
    directory.mkdir()
    (directory / "broken.manifest.json").write_text(body, encoding="utf-8")

    with pytest.raises(RecordedCorpusError):
        RecordedWaCorpus(tmp_path)


def test_manifest_without_a_declared_content_file_refuses_to_load(tmp_path: Path) -> None:
    directory = tmp_path / "broken"
    directory.mkdir()
    (directory / "broken.manifest.json").write_text(
        json.dumps({"source_system": "wa_legislation"}), encoding="utf-8"
    )

    with pytest.raises(RecordedCorpusError):
        RecordedWaCorpus(tmp_path)


def test_absent_corpus_root_refuses_to_load(tmp_path: Path) -> None:
    with pytest.raises(RecordedCorpusError):
        RecordedWaCorpus(tmp_path / "does-not-exist")


def test_malformed_provision_entries_are_dropped_rather_than_trusted(tmp_path: Path) -> None:
    corpus = RecordedWaCorpus(
        _write_corpus(
            tmp_path,
            provisions=[
                "s 55",
                {"identifier": "s 56"},
                {"identifier": "", "pinpoint": "section 57"},
                {"identifier": "s 58", "pinpoint": "   "},
                {"identifier": "s 59", "pinpoint": "section 59", "heading": None},
            ],
        )
    )

    source = corpus.select(recorded_query(act_title="Synthetic Act 1974"))

    assert source is not None
    assert [provision.identifier for provision in source.provisions] == ["s 59"]
    assert source.provisions[0].heading is None


def test_non_string_manifest_values_are_not_coerced(tmp_path: Path) -> None:
    corpus = RecordedWaCorpus(
        _write_corpus(
            tmp_path,
            source_system=["wa_legislation"],
            jurisdiction=1,
            status={"currency": "Current", "in_force": "yes", "status_date": "2025-01-10"},
        )
    )

    source = corpus.select(recorded_query(act_title="Synthetic Act 1974"))

    assert source is not None
    assert source.source_system is None
    assert source.jurisdiction is None
    assert source.status_in_force is None
