"""Offline tests for ``scripts/ingest_wa_act.py``.

The download path is always mocked with ``httpx.MockTransport`` serving the
committed official fixture bytes from disk; no test touches the network.
Each run writes only under the injected ``tmp_path`` fixture root.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
import pytest
from scripts.ingest_wa_act import main

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "wa_legislation"
_SOG_PDF = _FIXTURES / "sale_of_goods_act_1895" / "sale_of_goods_act_1895_consolidated_05-d0-06.pdf"
_PDF_URL = (
    "https://www.legislation.wa.gov.au/legislation/statutes.nsf/"
    "RedirectURL?OpenAgent&query=mrdoc_19856.pdf"
)
_PAGE_URL = "https://www.legislation.wa.gov.au/legislation/statutes.nsf/law_a726.html"
_TITLE = "Sale of Goods Act 1895"


def _args(root: Path, sections: str, **overrides: str) -> list[str]:
    values: dict[str, str] = {
        "--root": str(root),
        "--slug": "demo_act_1895",
        "--act-title": _TITLE,
        "--act-number": "041 of 1895 (59Vict No 41)",
        "--assent-date": "1895-10-12",
        "--version-suffix": "05-d0-06",
        "--currency-start": "2010-09-11",
        "--status-date": "2010-09-11",
        "--act-page-url": _PAGE_URL,
        "--pdf-url": _PDF_URL,
        "--sections": sections,
    }
    values.update(overrides)
    return [item for pair in values.items() for item in pair]


def _serve(payload: bytes) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            content=payload,
            headers={"content-type": "application/pdf"},
        )

    return httpx.MockTransport(handler)


def _client(payload: bytes) -> httpx.Client:
    return httpx.Client(transport=_serve(payload), follow_redirects=True)


def _boom_client() -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("network must not be touched for a refused run")

    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def _textless_pdf() -> bytes:
    """Return a small but valid PDF whose text layer holds only 'Hello'."""

    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>\nendobj\n",
        b"4 0 obj\n<< /Length 42 >>\nstream\nBT /F1 24 Tf 72 720 Td (Hello) Tj ET\n"
        b"endstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out += obj
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(out)


def test_happy_path_ingests_one_act_with_manifest_and_derived_provisions(tmp_path: Path) -> None:
    payload = _SOG_PDF.read_bytes()

    exit_code = main(_args(tmp_path, "s 14"), client=_client(payload))

    assert exit_code == 0
    directory = tmp_path / "demo_act_1895"
    manifest_path = directory / "demo_act_1895_consolidated_05-d0-06.manifest.json"
    pdf_path = directory / "demo_act_1895_consolidated_05-d0-06.pdf"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["source_id"] == "wa_legislation:demo_act_1895:consolidated:05-d0-06"
    assert manifest["source_system"] == "wa_legislation"
    assert manifest["jurisdiction"] == "WA"
    assert manifest["act"]["title"] == _TITLE
    assert manifest["act"]["act_number"] == "041 of 1895 (59Vict No 41)"
    assert manifest["act"]["assent_date"] == "1895-10-12"
    assert manifest["version"]["suffix"] == "05-d0-06"
    assert manifest["version"]["document_id"] == "mrdoc_19856"
    assert manifest["request"]["url"] == _PDF_URL
    assert manifest["official_source_url"] == f"{_PAGE_URL}&view=consolidated"
    assert manifest["sha256"] == hashlib.sha256(payload).hexdigest()
    assert manifest["content_length"] == len(payload)
    assert manifest["file"] == "demo_act_1895_consolidated_05-d0-06.pdf"
    assert manifest["provisions"] == [
        {
            "identifier": "s 14",
            "pinpoint": "section 14",
            "heading": "Implied conditions as to quality or fitness",
        }
    ]

    assert pdf_path.read_bytes() == payload
    assert (directory / "README.md").is_file()

    provision_path = directory / "provisions" / "s_14.provision.json"
    text_path = directory / "provisions" / "s_14.txt"
    assert provision_path.is_file()
    assert text_path.is_file()
    provision = json.loads(provision_path.read_text(encoding="utf-8"))
    assert provision["parent_sha256"] == manifest["sha256"]
    assert provision["source_version"] == manifest["version"]["suffix"]
    assert provision["provision_identifier"] == "s 14"
    assert provision["heading"] == "Implied conditions as to quality or fitness"
    assert provision["sha256"] == hashlib.sha256(text_path.read_bytes()).hexdigest()
    assert provision["byte_length"] == text_path.stat().st_size


def test_multiple_sections_are_all_recorded_when_all_confirmed(tmp_path: Path) -> None:
    payload = _SOG_PDF.read_bytes()

    exit_code = main(_args(tmp_path, "s 13,s 14"), client=_client(payload))

    assert exit_code == 0
    manifest_path = tmp_path / "demo_act_1895" / "demo_act_1895_consolidated_05-d0-06.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert [entry["identifier"] for entry in manifest["provisions"]] == ["s 13", "s 14"]
    assert (tmp_path / "demo_act_1895" / "provisions" / "s_13.txt").is_file()
    assert (tmp_path / "demo_act_1895" / "provisions" / "s_14.txt").is_file()


def test_digest_mismatch_refuses_and_writes_nothing(tmp_path: Path) -> None:
    payload = _SOG_PDF.read_bytes()
    wrong = "0" * 64

    exit_code = main(
        _args(tmp_path, "s 14", **{"--expected-sha256": wrong}), client=_client(payload)
    )

    assert exit_code == 1
    assert not (tmp_path / "demo_act_1895").exists()


def test_all_sections_missing_refuses_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = _SOG_PDF.read_bytes()

    exit_code = main(_args(tmp_path, "s 999"), client=_client(payload))

    assert exit_code == 1
    assert not (tmp_path / "demo_act_1895").exists()
    assert "MISSING s 999" in capsys.readouterr().out


def test_partial_missing_records_confirmed_sections_and_reports_the_rest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = _SOG_PDF.read_bytes()

    exit_code = main(_args(tmp_path, "s 14,s 999"), client=_client(payload))

    assert exit_code == 2
    manifest_path = tmp_path / "demo_act_1895" / "demo_act_1895_consolidated_05-d0-06.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert [entry["identifier"] for entry in manifest["provisions"]] == ["s 14"]
    assert (tmp_path / "demo_act_1895" / "provisions" / "s_14.txt").is_file()
    assert not (tmp_path / "demo_act_1895" / "provisions" / "s_999.txt").exists()
    assert "MISSING s 999" in capsys.readouterr().out


def test_wrong_host_url_refuses_before_any_network_call(tmp_path: Path) -> None:
    overrides = {"--pdf-url": "https://evil.example.com/pdfs/mrdoc_19856.pdf"}

    exit_code = main(_args(tmp_path, "s 14", **overrides), client=_boom_client())

    assert exit_code == 1
    assert not (tmp_path / "demo_act_1895").exists()


def test_non_https_act_page_refuses_before_any_network_call(tmp_path: Path) -> None:
    overrides = {"--act-page-url": "http://www.legislation.wa.gov.au/law_a726.html"}

    exit_code = main(_args(tmp_path, "s 14", **overrides), client=_boom_client())

    assert exit_code == 1
    assert not (tmp_path / "demo_act_1895").exists()


def test_missing_text_layer_refuses_and_writes_nothing(tmp_path: Path) -> None:
    exit_code = main(_args(tmp_path, "s 14"), client=_client(_textless_pdf()))

    assert exit_code == 1
    assert not (tmp_path / "demo_act_1895").exists()


def test_existing_fixture_directory_refuses_and_leaves_it_untouched(tmp_path: Path) -> None:
    payload = _SOG_PDF.read_bytes()
    existing = tmp_path / "demo_act_1895"
    marker = existing / "existing.txt"
    marker.parent.mkdir(parents=True)
    marker.write_text("keep me", encoding="utf-8")

    exit_code = main(_args(tmp_path, "s 14"), client=_client(payload))

    assert exit_code == 1
    assert marker.read_text(encoding="utf-8") == "keep me"


def test_malformed_section_identifier_refuses(tmp_path: Path) -> None:
    exit_code = main(_args(tmp_path, "14"), client=_boom_client())

    assert exit_code == 1
    assert not (tmp_path / "demo_act_1895").exists()
