"""Unit tests for Phase 4 Slice 2: recorded section body-text records (ADR 0014)."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

import pytest

from legal_ai.research.corpus import RecordedWaCorpus
from legal_ai.research.models import RecordedSection
from tests.research.conftest import RECORDED_FIXTURE_ROOT, recorded_source

_SECTIONS_FILE = (
    RECORDED_FIXTURE_ROOT
    / "road_traffic_act_1974"
    / "road_traffic_act_1974_consolidated_14-t0-00.sections.json"
)
_S55_HEADING = "Driver in incident occasioning property damage to stop and give information"
_S56_HEADING = (
    "Driver in incident occasioning bodily harm or property damage to report incident to police"
)


# ---------------------------------------------------------------------------
# RecordedSection model
# ---------------------------------------------------------------------------


def test_recorded_section_defaults_to_unverified() -> None:
    section = RecordedSection(
        identifier="s 1",
        heading=None,
        text="Text.",
        text_sha256="a" * 64,
    )

    assert section.verified is False


def test_recorded_section_is_immutable() -> None:
    section = RecordedSection(
        identifier="s 1",
        heading=None,
        text="Text.",
        text_sha256="a" * 64,
    )

    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        section.verified = True  # type: ignore[misc]


def test_recorded_section_with_no_heading() -> None:
    section = RecordedSection(
        identifier="s 1",
        heading=None,
        text="Text.",
        text_sha256="a" * 64,
    )

    assert section.heading is None


def test_recorded_wa_source_sections_defaults_to_empty_tuple() -> None:
    source = recorded_source()

    assert source.sections == ()
    assert isinstance(source.sections, tuple)


# ---------------------------------------------------------------------------
# Corpus sections loading
# ---------------------------------------------------------------------------


def _write_corpus_with_sections(
    tmp_path: Path, sections_data: object | None = None
) -> RecordedWaCorpus:
    """Write a minimal corpus with an optional sections JSON to tmp_path."""
    content = b"synthetic content"
    sha256 = hashlib.sha256(content).hexdigest()
    manifest = {
        "source_id": "wa_legislation:synthetic:consolidated:1-a0-00",
        "source_system": "wa_legislation",
        "jurisdiction": "WA",
        "act": {"title": "Synthetic Act 1974", "jurisdiction": "WA"},
        "provisions": [{"identifier": "s 1", "pinpoint": "section 1"}],
        "version": {"suffix": "1-a0-00", "currency_start": "2025-01-10"},
        "status": {"currency": "Current", "in_force": True, "status_date": "2025-01-10"},
        "official_source_url": "https://www.legislation.wa.gov.au/legislation/law_s1.html",
        "retrieved_at_utc": "2026-08-11T10:27:03Z",
        "sha256": sha256,
        "file": "synthetic.pdf",
    }
    act_dir = tmp_path / "synthetic"
    act_dir.mkdir()
    (act_dir / "synthetic.pdf").write_bytes(content)
    (act_dir / "synthetic.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if sections_data is not None:
        (act_dir / "synthetic.sections.json").write_text(
            json.dumps(sections_data), encoding="utf-8"
        )
    return RecordedWaCorpus(tmp_path)


def test_corpus_loads_sections_when_file_present(tmp_path: Path) -> None:
    sections_data = {
        "sections": [
            {
                "identifier": "s 1",
                "heading": "A heading",
                "text": "Section one text.",
                "text_sha256": hashlib.sha256(b"Section one text.").hexdigest(),
                "verified": False,
            }
        ]
    }
    corpus = _write_corpus_with_sections(tmp_path, sections_data)
    from legal_ai.research.models import ResearchQuery

    source = corpus.select(
        ResearchQuery(
            jurisdiction="WA",
            act_title="Synthetic Act 1974",
            provision_identifier="s 1",
            pinpoint="section 1",
        )
    )

    assert source is not None
    assert len(source.sections) == 1
    assert source.sections[0].identifier == "s 1"
    assert source.sections[0].heading == "A heading"
    assert source.sections[0].text == "Section one text."
    assert source.sections[0].verified is False


def test_corpus_sections_empty_when_file_absent(tmp_path: Path) -> None:
    corpus = _write_corpus_with_sections(tmp_path, sections_data=None)
    from legal_ai.research.models import ResearchQuery

    source = corpus.select(
        ResearchQuery(
            jurisdiction="WA",
            act_title="Synthetic Act 1974",
            provision_identifier="s 1",
            pinpoint="section 1",
        )
    )

    assert source is not None
    assert source.sections == ()


def test_corpus_sections_empty_on_malformed_json(tmp_path: Path) -> None:
    content = b"synthetic content"
    sha256 = hashlib.sha256(content).hexdigest()
    manifest = {
        "source_id": "wa_legislation:synthetic:consolidated:1-a0-00",
        "source_system": "wa_legislation",
        "jurisdiction": "WA",
        "act": {"title": "Synthetic Act 1974", "jurisdiction": "WA"},
        "provisions": [{"identifier": "s 1", "pinpoint": "section 1"}],
        "version": {"suffix": "1-a0-00", "currency_start": "2025-01-10"},
        "status": {"currency": "Current", "in_force": True, "status_date": "2025-01-10"},
        "official_source_url": "https://www.legislation.wa.gov.au/legislation/law_s1.html",
        "retrieved_at_utc": "2026-08-11T10:27:03Z",
        "sha256": sha256,
        "file": "synthetic.pdf",
    }
    act_dir = tmp_path / "synthetic"
    act_dir.mkdir()
    (act_dir / "synthetic.pdf").write_bytes(content)
    (act_dir / "synthetic.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (act_dir / "synthetic.sections.json").write_text("not valid json {{{{", encoding="utf-8")
    corpus = RecordedWaCorpus(tmp_path)
    from legal_ai.research.models import ResearchQuery

    source = corpus.select(
        ResearchQuery(
            jurisdiction="WA",
            act_title="Synthetic Act 1974",
            provision_identifier="s 1",
            pinpoint="section 1",
        )
    )

    assert source is not None
    assert source.sections == ()


def test_corpus_sections_skips_entry_missing_identifier(tmp_path: Path) -> None:
    sections_data = {
        "sections": [
            {
                "heading": "A heading",
                "text": "Text.",
                "text_sha256": hashlib.sha256(b"Text.").hexdigest(),
            }
        ]
    }
    corpus = _write_corpus_with_sections(tmp_path, sections_data)
    from legal_ai.research.models import ResearchQuery

    source = corpus.select(
        ResearchQuery(
            jurisdiction="WA",
            act_title="Synthetic Act 1974",
            provision_identifier="s 1",
            pinpoint="section 1",
        )
    )

    assert source is not None
    assert source.sections == ()


def test_corpus_sections_skips_entry_missing_text(tmp_path: Path) -> None:
    sections_data = {
        "sections": [
            {
                "identifier": "s 1",
                "heading": "A heading",
                "text_sha256": hashlib.sha256(b"Text.").hexdigest(),
            }
        ]
    }
    corpus = _write_corpus_with_sections(tmp_path, sections_data)
    from legal_ai.research.models import ResearchQuery

    source = corpus.select(
        ResearchQuery(
            jurisdiction="WA",
            act_title="Synthetic Act 1974",
            provision_identifier="s 1",
            pinpoint="section 1",
        )
    )

    assert source is not None
    assert source.sections == ()


def test_corpus_sections_skips_entry_missing_text_sha256(tmp_path: Path) -> None:
    sections_data = {"sections": [{"identifier": "s 1", "heading": "A heading", "text": "Text."}]}
    corpus = _write_corpus_with_sections(tmp_path, sections_data)
    from legal_ai.research.models import ResearchQuery

    source = corpus.select(
        ResearchQuery(
            jurisdiction="WA",
            act_title="Synthetic Act 1974",
            provision_identifier="s 1",
            pinpoint="section 1",
        )
    )

    assert source is not None
    assert source.sections == ()


def test_corpus_sections_empty_when_sections_file_is_symlink_inside_root(tmp_path: Path) -> None:
    content = b"synthetic content"
    sha256 = hashlib.sha256(content).hexdigest()
    manifest = {
        "source_id": "wa_legislation:synthetic:consolidated:1-a0-00",
        "source_system": "wa_legislation",
        "jurisdiction": "WA",
        "act": {"title": "Synthetic Act 1974", "jurisdiction": "WA"},
        "provisions": [{"identifier": "s 1", "pinpoint": "section 1"}],
        "version": {"suffix": "1-a0-00", "currency_start": "2025-01-10"},
        "status": {"currency": "Current", "in_force": True, "status_date": "2025-01-10"},
        "official_source_url": "https://www.legislation.wa.gov.au/legislation/law_s1.html",
        "retrieved_at_utc": "2026-08-11T10:27:03Z",
        "sha256": sha256,
        "file": "synthetic.pdf",
    }
    act_dir = tmp_path / "synthetic"
    act_dir.mkdir()
    (act_dir / "synthetic.pdf").write_bytes(content)
    (act_dir / "synthetic.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    text = "Section one text."
    sections_data = {
        "sections": [
            {
                "identifier": "s 1",
                "text": text,
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            }
        ]
    }
    real_file = tmp_path / "real.sections.json"
    real_file.write_text(json.dumps(sections_data), encoding="utf-8")
    (act_dir / "synthetic.sections.json").symlink_to(real_file)

    corpus = RecordedWaCorpus(tmp_path)
    from legal_ai.research.models import ResearchQuery

    source = corpus.select(
        ResearchQuery(
            jurisdiction="WA",
            act_title="Synthetic Act 1974",
            provision_identifier="s 1",
            pinpoint="section 1",
        )
    )

    assert source is not None
    assert source.sections == ()


def test_corpus_sections_empty_when_sections_file_is_symlink_outside_root(tmp_path: Path) -> None:
    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir()
    content = b"synthetic content"
    sha256 = hashlib.sha256(content).hexdigest()
    manifest = {
        "source_id": "wa_legislation:synthetic:consolidated:1-a0-00",
        "source_system": "wa_legislation",
        "jurisdiction": "WA",
        "act": {"title": "Synthetic Act 1974", "jurisdiction": "WA"},
        "provisions": [{"identifier": "s 1", "pinpoint": "section 1"}],
        "version": {"suffix": "1-a0-00", "currency_start": "2025-01-10"},
        "status": {"currency": "Current", "in_force": True, "status_date": "2025-01-10"},
        "official_source_url": "https://www.legislation.wa.gov.au/legislation/law_s1.html",
        "retrieved_at_utc": "2026-08-11T10:27:03Z",
        "sha256": sha256,
        "file": "synthetic.pdf",
    }
    act_dir = corpus_root / "synthetic"
    act_dir.mkdir()
    (act_dir / "synthetic.pdf").write_bytes(content)
    (act_dir / "synthetic.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    text = "Section one text."
    sections_data = {
        "sections": [
            {
                "identifier": "s 1",
                "text": text,
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            }
        ]
    }
    outside_file = tmp_path / "outside.sections.json"
    outside_file.write_text(json.dumps(sections_data), encoding="utf-8")
    (act_dir / "synthetic.sections.json").symlink_to(outside_file)

    corpus = RecordedWaCorpus(corpus_root)
    from legal_ai.research.models import ResearchQuery

    source = corpus.select(
        ResearchQuery(
            jurisdiction="WA",
            act_title="Synthetic Act 1974",
            provision_identifier="s 1",
            pinpoint="section 1",
        )
    )

    assert source is not None
    assert source.sections == ()


def test_corpus_sections_verified_requires_exact_python_true(tmp_path: Path) -> None:
    text = "Section one text."
    sections_data = {
        "sections": [
            {
                "identifier": "s 1",
                "text": text,
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "verified": "yes",
            },
            {
                "identifier": "s 2",
                "text": text,
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "verified": 1,
            },
            {
                "identifier": "s 3",
                "text": text,
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "verified": None,
            },
        ]
    }
    corpus = _write_corpus_with_sections(tmp_path, sections_data)
    from legal_ai.research.models import ResearchQuery

    source = corpus.select(
        ResearchQuery(
            jurisdiction="WA",
            act_title="Synthetic Act 1974",
            provision_identifier="s 1",
            pinpoint="section 1",
        )
    )

    assert source is not None
    assert len(source.sections) == 3
    for section in source.sections:
        assert section.verified is False, f"{section.identifier} should not be verified"


# ---------------------------------------------------------------------------
# Real fixture tests
# ---------------------------------------------------------------------------


def _real_corpus() -> RecordedWaCorpus:
    return RecordedWaCorpus(RECORDED_FIXTURE_ROOT)


def _real_sections() -> tuple[RecordedSection, ...]:
    from legal_ai.research.models import ResearchQuery

    source = _real_corpus().select(
        ResearchQuery(
            jurisdiction="WA",
            act_title="Road Traffic Act 1974",
            provision_identifier="s 55",
            pinpoint="section 55",
        )
    )
    assert source is not None
    return source.sections


def test_real_fixture_sections_are_loaded() -> None:
    sections = _real_sections()

    assert sections is not None
    assert isinstance(sections, tuple)


def test_real_fixture_has_exactly_two_sections() -> None:
    sections = _real_sections()

    assert len(sections) == 2


def test_real_fixture_s55_identifier_and_heading() -> None:
    sections = _real_sections()
    s55 = next((s for s in sections if s.identifier == "s 55"), None)

    assert s55 is not None
    assert s55.heading == _S55_HEADING


def test_real_fixture_s56_identifier_and_heading() -> None:
    sections = _real_sections()
    s56 = next((s for s in sections if s.identifier == "s 56"), None)

    assert s56 is not None
    assert s56.heading == _S56_HEADING


def test_real_fixture_s55_is_not_verified() -> None:
    sections = _real_sections()
    s55 = next((s for s in sections if s.identifier == "s 55"), None)

    assert s55 is not None
    assert s55.verified is False


def test_real_fixture_s56_is_not_verified() -> None:
    sections = _real_sections()
    s56 = next((s for s in sections if s.identifier == "s 56"), None)

    assert s56 is not None
    assert s56.verified is False


@pytest.mark.parametrize("identifier", ["s 55", "s 56"])
def test_real_fixture_section_digest_integrity(identifier: str) -> None:
    sections = _real_sections()
    section = next((s for s in sections if s.identifier == identifier), None)

    assert section is not None
    assert hashlib.sha256(section.text.encode("utf-8")).hexdigest() == section.text_sha256


def test_real_fixture_sections_are_independent_of_corpus_instance() -> None:
    first = _real_sections()
    second = _real_sections()

    assert first == second
    assert first is not second
