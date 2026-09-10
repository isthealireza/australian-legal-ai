"""Derived provision text must be refused unless its whole chain verifies."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from legal_ai.answering.provisions import (
    FileDerivedProvisionStore,
    NullDerivedProvisionStore,
)
from tests.answering.conftest import build_packet, build_recorded_packet
from tests.research.conftest import RECORDED_FIXTURE_ROOT

PROVISION_DIR = RECORDED_FIXTURE_ROOT / "road_traffic_act_1974" / "provisions"


def _copy_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "wa_legislation"
    shutil.copytree(RECORDED_FIXTURE_ROOT, root)
    return root


def test_resolves_text_whose_chain_matches_the_packet() -> None:
    packet = build_recorded_packet()
    provision = FileDerivedProvisionStore(RECORDED_FIXTURE_ROOT).resolve(packet)
    assert provision is not None
    assert provision.provision_identifier == packet.provision_identifier
    assert provision.pinpoint == packet.pinpoint
    assert provision.parent_sha256 == packet.sha256
    assert "the driver must stop" in provision.text


def test_recorded_text_digest_matches_its_manifest() -> None:
    for manifest_path in PROVISION_DIR.glob("*.provision.json"):
        record = json.loads(manifest_path.read_text(encoding="utf-8"))
        content = (manifest_path.parent / record["file"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == record["sha256"]


def test_packet_from_a_different_source_resolves_nothing() -> None:
    """A synthetic packet has no derived text, so nothing may be attached."""

    assert FileDerivedProvisionStore(RECORDED_FIXTURE_ROOT).resolve(build_packet()) is None


def test_tampered_text_is_refused(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    target = root / "road_traffic_act_1974" / "provisions" / "s_55.txt"
    target.write_text("55. Rewritten by someone who should not have.", encoding="utf-8")
    assert FileDerivedProvisionStore(root).resolve(build_recorded_packet()) is None


def test_forged_parent_digest_is_refused(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    manifest = root / "road_traffic_act_1974" / "provisions" / "s_55.provision.json"
    record = json.loads(manifest.read_text(encoding="utf-8"))
    record["parent_sha256"] = hashlib.sha256(b"not the real act").hexdigest()
    manifest.write_text(json.dumps(record), encoding="utf-8")
    assert FileDerivedProvisionStore(root).resolve(build_recorded_packet()) is None


def test_mismatched_pinpoint_is_refused(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    manifest = root / "road_traffic_act_1974" / "provisions" / "s_55.provision.json"
    record = json.loads(manifest.read_text(encoding="utf-8"))
    record["pinpoint"] = "section 999"
    manifest.write_text(json.dumps(record), encoding="utf-8")
    assert FileDerivedProvisionStore(root).resolve(build_recorded_packet()) is None


def test_filename_escaping_the_root_is_refused(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    manifest = root / "road_traffic_act_1974" / "provisions" / "s_55.provision.json"
    record = json.loads(manifest.read_text(encoding="utf-8"))
    record["file"] = "../../../../etc/passwd"
    manifest.write_text(json.dumps(record), encoding="utf-8")
    assert FileDerivedProvisionStore(root).resolve(build_recorded_packet()) is None


def test_malformed_manifest_is_skipped(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    manifest = root / "road_traffic_act_1974" / "provisions" / "s_55.provision.json"
    manifest.write_text("{ not json", encoding="utf-8")
    assert FileDerivedProvisionStore(root).resolve(build_recorded_packet()) is None


def test_missing_root_resolves_nothing(tmp_path: Path) -> None:
    store = FileDerivedProvisionStore(tmp_path / "does-not-exist")
    assert store.resolve(build_recorded_packet()) is None


def test_null_store_resolves_nothing() -> None:
    assert NullDerivedProvisionStore().resolve(build_recorded_packet()) is None
