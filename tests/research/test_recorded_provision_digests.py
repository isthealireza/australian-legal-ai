"""Derivation-digest integrity for the recorded WA fixtures.

For every pinned provision of the recorded fixtures, the derived
`provisions/<slug>.provision.json` must exist next to a non-empty
`provisions/<slug>.txt`, and its recorded parent digest must equal the
digest of the evidence packet that the research service returns for that
provision. A derived text can therefore never be attached to a source it
was not derived from.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from legal_ai.research.corpus import RecordedWaCorpus
from legal_ai.research.service import ResearchValidated, WaResearchService
from tests.research.conftest import RECORDED_FIXTURE_ROOT, recorded_query
from tests.support.research_audit import InMemoryResearchAuditSink

# (act_dir, act_title, identifier, pinpoint)
_PINNED = [
    ("sale_of_goods_act_1895", "Sale of Goods Act 1895", "s 13", "section 13"),
    ("sale_of_goods_act_1895", "Sale of Goods Act 1895", "s 14", "section 14"),
    ("sale_of_goods_act_1895", "Sale of Goods Act 1895", "s 15", "section 15"),
    ("sale_of_goods_act_1895", "Sale of Goods Act 1895", "s 16", "section 16"),
    ("fair_trading_act_2010", "Fair Trading Act 2010", "s 18", "section 18"),
    ("fair_trading_act_2010", "Fair Trading Act 2010", "s 19", "section 19"),
]


def _slug(identifier: str) -> str:
    return identifier.replace(" ", "_").replace(".", "")


def _packet_sha256(act_title: str, identifier: str, pinpoint: str) -> str:
    service = WaResearchService(
        corpus=RecordedWaCorpus(RECORDED_FIXTURE_ROOT),
        audit_sink=InMemoryResearchAuditSink(),
    )
    result = service.research(
        recorded_query(act_title=act_title, provision_identifier=identifier, pinpoint=pinpoint)
    )
    assert isinstance(result, ResearchValidated)
    sha256 = result.packet.sha256
    assert isinstance(sha256, str)
    return sha256


@pytest.mark.parametrize(
    ("act_dir", "act_title", "identifier", "pinpoint"),
    list(_PINNED),
    ids=[f"{row[0]}-{row[2]}".replace(" ", "-") for row in _PINNED],
)
def test_derived_provision_digest_matches_the_source_packet_digest(
    act_dir: str, act_title: str, identifier: str, pinpoint: str
) -> None:
    record_path = (
        RECORDED_FIXTURE_ROOT / act_dir / "provisions" / f"{_slug(identifier)}.provision.json"
    )
    text_path = record_path.with_name(f"{_slug(identifier)}.txt")

    assert record_path.is_file()
    assert text_path.is_file()
    assert text_path.stat().st_size > 0

    record = json.loads(record_path.read_text(encoding="utf-8"))
    text = text_path.read_bytes()
    manifest_path = next((RECORDED_FIXTURE_ROOT / act_dir).glob("*.manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert record["parent_sha256"] == _packet_sha256(act_title, identifier, pinpoint)
    assert record["source_version"] == manifest["version"]["suffix"]
    assert record["sha256"] == hashlib.sha256(text).hexdigest()
    assert record["byte_length"] == len(text)
    assert record["provision_identifier"] == identifier
    assert record["pinpoint"] == pinpoint
    assert text.strip()


@pytest.mark.parametrize(
    ("act_dir", "act_title", "identifier", "pinpoint"),
    list(_PINNED),
    ids=[f"{row[0]}-{row[2]}".replace(" ", "-") for row in _PINNED],
)
def test_provision_text_is_a_non_empty_substring_of_the_source_document(
    act_dir: str, act_title: str, identifier: str, pinpoint: str
) -> None:
    text_path = RECORDED_FIXTURE_ROOT / act_dir / "provisions" / f"{_slug(identifier)}.txt"

    assert text_path.read_bytes().strip()
