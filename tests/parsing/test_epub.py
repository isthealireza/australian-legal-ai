import hashlib
import stat
import warnings
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path
from xml.etree import ElementTree

import pytest
from pydantic import ValidationError

from legal_ai.parsing import (
    EpubParseError,
    EpubParseLimits,
    EpubSecurityError,
    EpubUnsupportedFeatureError,
    EpubValidationError,
    ParsedEpubDocument,
    parse_epub,
)

FIXTURES = Path(__file__).parent / "fixtures"


@dataclass(frozen=True, slots=True)
class _ZipEntry:
    name: str
    data: bytes
    compression: int
    unix_mode: int = stat.S_IFREG | 0o644


def _limits(**overrides: object) -> EpubParseLimits:
    values: dict[str, object] = {
        "maximum_archive_bytes": 100_000,
        "maximum_entry_count": 20,
        "maximum_entry_uncompressed_bytes": 20_000,
        "maximum_total_uncompressed_bytes": 50_000,
        "maximum_compression_ratio": 100.0,
        "maximum_xhtml_block_count": 100,
        "maximum_text_characters_per_block": 1_000,
    }
    values.update(overrides)
    return EpubParseLimits.model_validate(values)


def _parse_artifact(
    artifact: Path,
    *,
    expected_sha256: str | None = None,
    **limit_overrides: object,
) -> ParsedEpubDocument:
    return parse_epub(
        artifact,
        expected_sha256=expected_sha256 or hashlib.sha256(artifact.read_bytes()).hexdigest(),
        limits=_limits(**limit_overrides),
    )


def _fixture_entries(name: str = "minimal_valid.epub") -> list[_ZipEntry]:
    with zipfile.ZipFile(FIXTURES / name, "r") as archive:
        return [
            _ZipEntry(
                name=entry.filename,
                data=archive.read(entry),
                compression=entry.compress_type,
                unix_mode=entry.external_attr >> 16,
            )
            for entry in archive.infolist()
        ]


def _write_epub(tmp_path: Path, entries: list[_ZipEntry]) -> Path:
    artifact = tmp_path / "synthetic.epub"
    with warnings.catch_warnings(), zipfile.ZipFile(artifact, "w") as archive:
        warnings.simplefilter("ignore", UserWarning)
        for entry in entries:
            info = zipfile.ZipInfo(entry.name, date_time=(2020, 1, 1, 0, 0, 0))
            info.filename = entry.name
            info.create_system = 3
            info.external_attr = entry.unix_mode << 16
            info.compress_type = entry.compression
            archive.writestr(
                info,
                entry.data,
                compress_type=entry.compression,
                compresslevel=9,
            )
    return artifact


def _mark_entry_encrypted(artifact: Path, target_name: str) -> None:
    payload = bytearray(artifact.read_bytes())
    signatures = (
        (b"PK\x03\x04", 6, 26, 28, 30),
        (b"PK\x01\x02", 8, 28, 30, 46),
    )
    matches = 0
    for signature, flag_offset, name_length_offset, _extra_length_offset, name_offset in signatures:
        offset = 0
        while (offset := payload.find(signature, offset)) != -1:
            name_length = int.from_bytes(
                payload[offset + name_length_offset : offset + name_length_offset + 2],
                "little",
            )
            encoded_name = payload[offset + name_offset : offset + name_offset + name_length]
            if encoded_name.decode("utf-8") == target_name:
                flags = int.from_bytes(
                    payload[offset + flag_offset : offset + flag_offset + 2],
                    "little",
                )
                payload[offset + flag_offset : offset + flag_offset + 2] = (flags | 1).to_bytes(
                    2,
                    "little",
                )
                matches += 1
            offset += len(signature)
    assert matches == 2
    artifact.write_bytes(payload)


def _rewrite_local_entry_name(artifact: Path, target_name: str, replacement: str) -> None:
    target_bytes = target_name.encode("utf-8")
    replacement_bytes = replacement.encode("utf-8")
    assert len(target_bytes) == len(replacement_bytes)
    payload = bytearray(artifact.read_bytes())
    offset = 0
    matches = 0
    while (offset := payload.find(b"PK\x03\x04", offset)) != -1:
        name_length = int.from_bytes(payload[offset + 26 : offset + 28], "little")
        name_start = offset + 30
        if payload[name_start : name_start + name_length] == target_bytes:
            payload[name_start : name_start + name_length] = replacement_bytes
            matches += 1
        offset += 4
    assert matches == 1
    artifact.write_bytes(payload)


def _replace_entry_data(
    entries: list[_ZipEntry],
    name: str,
    data: bytes,
) -> list[_ZipEntry]:
    return [replace(entry, data=data) if entry.name == name else entry for entry in entries]


def _container_xml(rootfiles: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
        f"<rootfiles>{rootfiles}</rootfiles></container>\n"
    ).encode()


def _package_xml(manifest: str, spine: str, *, include: str = "all") -> bytes:
    metadata = (
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        '<dc:identifier id="book-id">urn:test:variant</dc:identifier>'
        "<dc:title>Invented Variant</dc:title><dc:language>en-AU</dc:language></metadata>"
    )
    parts = {
        "metadata": metadata,
        "manifest": f"<manifest>{manifest}</manifest>",
        "spine": f"<spine>{spine}</spine>",
    }
    body = "".join(value for name, value in parts.items() if include == "all" or name != include)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
        f'unique-identifier="book-id">{body}</package>\n'
    ).encode()


def test_minimal_valid_epub_returns_ordered_strict_models() -> None:
    artifact = FIXTURES / "minimal_valid.epub"
    expected_sha256 = hashlib.sha256(artifact.read_bytes()).hexdigest()

    parsed = parse_epub(
        artifact,
        expected_sha256=expected_sha256,
        limits=_limits(),
    )

    assert parsed.artifact_sha256 == expected_sha256
    assert parsed.package_identifier == "urn:test:minimal"
    assert parsed.package_title == "Invented Structural Example"
    assert parsed.language == "en-AU"
    assert len(parsed.spine_documents) == 1
    document = parsed.spine_documents[0]
    assert document.spine_index == 0
    assert document.href == "EPUB/chapter.xhtml"
    assert document.declared_media_type == "application/xhtml+xml"
    assert document.document_title == "Invented Chapter"
    assert [block.normalized_text for block in document.blocks] == [
        "Invented heading",
        "Portable inline text remains ordered.",
    ]
    assert [block.locator for block in document.blocks] == [
        "EPUB/chapter.xhtml#heading",
        "EPUB/chapter.xhtml#paragraph",
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("maximum_archive_bytes", 0),
        ("maximum_entry_count", -1),
        ("maximum_entry_uncompressed_bytes", 0),
        ("maximum_total_uncompressed_bytes", -1),
        ("maximum_compression_ratio", 0.0),
        ("maximum_compression_ratio", float("inf")),
        ("maximum_xhtml_block_count", 0),
        ("maximum_text_characters_per_block", -1),
    ],
)
def test_parse_limits_reject_zero_or_negative_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        _limits(**{field: value})


def test_malformed_expected_sha256_is_rejected() -> None:
    with pytest.raises(EpubValidationError, match="64 lowercase"):
        _parse_artifact(FIXTURES / "minimal_valid.epub", expected_sha256="A" * 64)


def test_expected_sha256_mismatch_is_rejected() -> None:
    with pytest.raises(EpubValidationError, match="did not match"):
        _parse_artifact(FIXTURES / "minimal_valid.epub", expected_sha256="0" * 64)


def test_empty_artifact_is_rejected(tmp_path: Path) -> None:
    artifact = tmp_path / "empty.epub"
    artifact.touch()

    with pytest.raises(EpubValidationError, match="must not be empty"):
        parse_epub(artifact, expected_sha256=hashlib.sha256(b"").hexdigest(), limits=_limits())


def test_archive_exactly_at_byte_limit_is_accepted() -> None:
    artifact = FIXTURES / "minimal_valid.epub"

    parsed = _parse_artifact(artifact, maximum_archive_bytes=artifact.stat().st_size)

    assert parsed.package_identifier == "urn:test:minimal"


def test_source_artifact_is_not_modified_or_deleted() -> None:
    artifact = FIXTURES / "minimal_valid.epub"
    before = artifact.read_bytes()

    _parse_artifact(artifact)

    assert artifact.is_file()
    assert artifact.read_bytes() == before


def test_archive_one_byte_over_limit_is_rejected() -> None:
    artifact = FIXTURES / "minimal_valid.epub"

    with pytest.raises(EpubSecurityError, match="archive byte-size"):
        _parse_artifact(artifact, maximum_archive_bytes=artifact.stat().st_size - 1)


def test_symlink_artifact_is_rejected_where_supported(tmp_path: Path) -> None:
    link = tmp_path / "linked.epub"
    try:
        link.symlink_to((FIXTURES / "minimal_valid.epub").resolve())
    except OSError as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")

    with pytest.raises(EpubSecurityError, match="symlink"):
        _parse_artifact(link)


def test_missing_artifact_does_not_expose_raw_os_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.epub"

    with pytest.raises(EpubParseError) as caught:
        parse_epub(missing, expected_sha256="0" * 64, limits=_limits())

    assert isinstance(caught.value.__cause__, OSError)


def test_invalid_zip_is_rejected_without_raw_bad_zip_error(tmp_path: Path) -> None:
    artifact = tmp_path / "invalid.epub"
    artifact.write_bytes(b"not a ZIP container")

    with pytest.raises(EpubValidationError) as caught:
        _parse_artifact(artifact)

    assert isinstance(caught.value.__cause__, zipfile.BadZipFile)


def test_missing_mimetype_is_rejected(tmp_path: Path) -> None:
    entries = [entry for entry in _fixture_entries() if entry.name != "mimetype"]

    with pytest.raises(EpubValidationError, match="mimetype"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_incorrect_mimetype_is_rejected(tmp_path: Path) -> None:
    entries = [
        replace(entry, data=b"application/zip") if entry.name == "mimetype" else entry
        for entry in _fixture_entries()
    ]

    with pytest.raises(EpubValidationError, match="mimetype entry is incorrect"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_mimetype_must_be_first(tmp_path: Path) -> None:
    entries = _fixture_entries()
    entries[0], entries[1] = entries[1], entries[0]

    with pytest.raises(EpubValidationError, match="must be first"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_mimetype_must_be_uncompressed(tmp_path: Path) -> None:
    entries = [
        replace(entry, compression=zipfile.ZIP_DEFLATED) if entry.name == "mimetype" else entry
        for entry in _fixture_entries()
    ]

    with pytest.raises(EpubValidationError, match="without compression"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_encrypted_entry_is_rejected(tmp_path: Path) -> None:
    artifact = _write_epub(tmp_path, _fixture_entries())
    _mark_entry_encrypted(artifact, "EPUB/chapter.xhtml")

    with pytest.raises(EpubUnsupportedFeatureError, match="encrypted"):
        _parse_artifact(artifact)


@pytest.mark.parametrize("unsafe_name", ["/absolute.xhtml", "C:/drive.xhtml", "//host/share.xhtml"])
def test_absolute_drive_and_unc_entry_paths_are_rejected(
    tmp_path: Path,
    unsafe_name: str,
) -> None:
    entries = [*_fixture_entries(), _ZipEntry(unsafe_name, b"unsafe", zipfile.ZIP_STORED)]

    with pytest.raises(EpubSecurityError, match="must be relative"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_parent_path_traversal_entry_is_rejected(tmp_path: Path) -> None:
    entries = [*_fixture_entries(), _ZipEntry("../escape", b"unsafe", zipfile.ZIP_STORED)]

    with pytest.raises(EpubSecurityError, match="unsafe component"):
        _parse_artifact(_write_epub(tmp_path, entries))


@pytest.mark.parametrize("unsafe_name", ["EPUB//empty.xhtml", "EPUB/./dot.xhtml"])
def test_empty_or_dot_entry_components_are_rejected(
    tmp_path: Path,
    unsafe_name: str,
) -> None:
    entries = [*_fixture_entries(), _ZipEntry(unsafe_name, b"unsafe", zipfile.ZIP_STORED)]

    with pytest.raises(EpubSecurityError, match="unsafe component"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_backslash_entry_ambiguity_is_rejected(tmp_path: Path) -> None:
    entries = [*_fixture_entries(), _ZipEntry("EPUB\\escape", b"unsafe", zipfile.ZIP_STORED)]

    with pytest.raises(EpubSecurityError, match="ambiguous backslashes"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_duplicate_normalized_entry_is_rejected(tmp_path: Path) -> None:
    entries = [*_fixture_entries(), _fixture_entries()[-1]]

    with pytest.raises(EpubSecurityError, match="duplicate normalized entry"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_unicode_equivalent_entry_names_are_rejected_as_duplicates(tmp_path: Path) -> None:
    entries = [
        *_fixture_entries(),
        _ZipEntry("EPUB/café.xhtml", b"one", zipfile.ZIP_STORED),
        _ZipEntry("EPUB/cafe\u0301.xhtml", b"two", zipfile.ZIP_STORED),
    ]

    with pytest.raises(EpubSecurityError, match="duplicate normalized entry"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_zip_symlink_entry_is_rejected(tmp_path: Path) -> None:
    entries = [
        *_fixture_entries(),
        _ZipEntry(
            "EPUB/symlink",
            b"chapter.xhtml",
            zipfile.ZIP_STORED,
            stat.S_IFLNK | 0o777,
        ),
    ]

    with pytest.raises(EpubSecurityError, match="symlink entry"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_zip_special_file_entry_is_rejected(tmp_path: Path) -> None:
    entries = [
        *_fixture_entries(),
        _ZipEntry("EPUB/fifo", b"", zipfile.ZIP_STORED, stat.S_IFIFO | 0o644),
    ]

    with pytest.raises(EpubUnsupportedFeatureError, match="special-file"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_zip_entry_count_limit_is_enforced() -> None:
    artifact = FIXTURES / "minimal_valid.epub"
    with zipfile.ZipFile(artifact, "r") as archive:
        entry_count = len(archive.infolist())

    with pytest.raises(EpubSecurityError, match="entry-count"):
        _parse_artifact(artifact, maximum_entry_count=entry_count - 1)


def test_entry_count_limit_precedes_per_entry_local_header_work(tmp_path: Path) -> None:
    entries = [*_fixture_entries(), _ZipEntry("safe/x", b"unused", zipfile.ZIP_STORED)]
    artifact = _write_epub(tmp_path, entries)
    _rewrite_local_entry_name(artifact, "safe/x", "../bad")

    with pytest.raises(EpubSecurityError, match="entry-count"):
        _parse_artifact(artifact, maximum_entry_count=len(entries) - 1)


def test_unsafe_local_header_path_is_rejected_even_when_entry_is_unused(tmp_path: Path) -> None:
    entries = [*_fixture_entries(), _ZipEntry("safe/x", b"unused", zipfile.ZIP_STORED)]
    artifact = _write_epub(tmp_path, entries)
    _rewrite_local_entry_name(artifact, "safe/x", "../bad")

    with pytest.raises(EpubSecurityError, match="unsafe component"):
        _parse_artifact(artifact)


def test_local_and_central_entry_name_mismatch_is_rejected(tmp_path: Path) -> None:
    entries = [*_fixture_entries(), _ZipEntry("safe/x", b"unused", zipfile.ZIP_STORED)]
    artifact = _write_epub(tmp_path, entries)
    _rewrite_local_entry_name(artifact, "safe/x", "otherx")

    with pytest.raises(EpubValidationError, match="local and central entry names differ"):
        _parse_artifact(artifact)


def test_per_entry_uncompressed_limit_is_enforced() -> None:
    artifact = FIXTURES / "minimal_valid.epub"
    with zipfile.ZipFile(artifact, "r") as archive:
        maximum_entry_size = max(entry.file_size for entry in archive.infolist())

    with pytest.raises(EpubSecurityError, match="per-entry"):
        _parse_artifact(
            artifact,
            maximum_entry_uncompressed_bytes=maximum_entry_size - 1,
        )


def test_total_uncompressed_limit_is_enforced() -> None:
    artifact = FIXTURES / "minimal_valid.epub"
    with zipfile.ZipFile(artifact, "r") as archive:
        total_size = sum(entry.file_size for entry in archive.infolist())

    with pytest.raises(EpubSecurityError, match="total uncompressed"):
        _parse_artifact(artifact, maximum_total_uncompressed_bytes=total_size - 1)


def test_compression_ratio_limit_is_enforced() -> None:
    with pytest.raises(EpubSecurityError, match="compression-ratio"):
        _parse_artifact(FIXTURES / "minimal_valid.epub", maximum_compression_ratio=1.0)


def test_missing_container_xml_is_rejected(tmp_path: Path) -> None:
    entries = [entry for entry in _fixture_entries() if entry.name != "META-INF/container.xml"]

    with pytest.raises(EpubValidationError, match="container.xml"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_malformed_container_xml_is_rejected(tmp_path: Path) -> None:
    entries = _replace_entry_data(
        _fixture_entries(),
        "META-INF/container.xml",
        b"<container>",
    )

    with pytest.raises(EpubValidationError, match="XML is malformed"):
        _parse_artifact(_write_epub(tmp_path, entries))


@pytest.mark.parametrize(
    "declaration",
    [
        b'<!DOCTYPE container SYSTEM "https://example.invalid/container.dtd">',
        b'<!ENTITY external "forbidden">',
    ],
)
def test_doctype_and_entity_declarations_are_rejected(
    tmp_path: Path,
    declaration: bytes,
) -> None:
    original = _fixture_entries()[1].data
    entries = _replace_entry_data(
        _fixture_entries(),
        "META-INF/container.xml",
        declaration + original,
    )

    with pytest.raises(EpubSecurityError, match="declarations are forbidden"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_external_loading_processing_instruction_is_rejected(tmp_path: Path) -> None:
    original = _fixture_entries()[1].data
    declaration_end = original.index(b"?>") + 2
    xml = (
        original[:declaration_end]
        + b'<?xml-stylesheet href="https://example.invalid/style.xsl"?>'
        + original[declaration_end:]
    )
    entries = _replace_entry_data(_fixture_entries(), "META-INF/container.xml", xml)

    with pytest.raises(EpubSecurityError, match="processing instructions"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_utf16_xml_with_doctype_cannot_bypass_security_preflight(tmp_path: Path) -> None:
    xml = (
        '<?xml version="1.0" encoding="UTF-16"?>'
        '<!DOCTYPE container [<!ENTITY expanded "EXPANDED">]>'
        '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" '
        'version="1.0"><rootfiles>&expanded;</rootfiles></container>'
    ).encode("utf-16")
    entries = _replace_entry_data(_fixture_entries(), "META-INF/container.xml", xml)

    with pytest.raises(EpubUnsupportedFeatureError, match="UTF-8 is required"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_missing_opf_rootfile_is_rejected(tmp_path: Path) -> None:
    container = _container_xml(
        '<rootfile full-path="EPUB/missing.opf" media-type="application/oebps-package+xml"/>'
    )
    entries = _replace_entry_data(_fixture_entries(), "META-INF/container.xml", container)

    with pytest.raises(EpubValidationError, match="rootfile is missing"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_multiple_usable_rootfiles_are_rejected(tmp_path: Path) -> None:
    container = _container_xml(
        '<rootfile full-path="EPUB/package.opf" '
        'media-type="application/oebps-package+xml"/>'
        '<rootfile full-path="EPUB/other.opf" '
        'media-type="application/oebps-package+xml"/>'
    )
    entries = _replace_entry_data(_fixture_entries(), "META-INF/container.xml", container)

    with pytest.raises(EpubValidationError, match="exactly one usable rootfile"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_unsupported_container_version_is_rejected(tmp_path: Path) -> None:
    container = _container_xml(
        '<rootfile full-path="EPUB/package.opf" media-type="application/oebps-package+xml"/>'
    ).replace(b'version="1.0"', b'version="2.0"')
    entries = _replace_entry_data(_fixture_entries(), "META-INF/container.xml", container)

    with pytest.raises(EpubUnsupportedFeatureError, match="container version"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_escaped_opf_reference_is_rejected(tmp_path: Path) -> None:
    container = _container_xml(
        '<rootfile full-path="../package.opf" media-type="application/oebps-package+xml"/>'
    )
    entries = _replace_entry_data(_fixture_entries(), "META-INF/container.xml", container)

    with pytest.raises(EpubSecurityError, match="internal reference is unsafe"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_missing_manifest_target_is_rejected(tmp_path: Path) -> None:
    package = _package_xml(
        '<item id="chapter" href="missing.xhtml" media-type="application/xhtml+xml"/>',
        '<itemref idref="chapter"/>',
    )
    entries = _replace_entry_data(_fixture_entries(), "EPUB/package.opf", package)

    with pytest.raises(EpubValidationError, match="manifest target is missing"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_duplicate_manifest_id_is_rejected(tmp_path: Path) -> None:
    package = _package_xml(
        '<item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>',
        '<itemref idref="chapter"/>',
    )
    entries = _replace_entry_data(_fixture_entries(), "EPUB/package.opf", package)

    with pytest.raises(EpubValidationError, match="manifest ID is duplicated"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_duplicate_spine_reference_is_rejected(tmp_path: Path) -> None:
    package = _package_xml(
        '<item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>',
        '<itemref idref="chapter"/><itemref idref="chapter"/>',
    )
    entries = _replace_entry_data(_fixture_entries(), "EPUB/package.opf", package)

    with pytest.raises(EpubValidationError, match="spine reference is duplicated"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_non_xhtml_spine_item_is_rejected(tmp_path: Path) -> None:
    package = _package_xml(
        '<item id="chapter" href="chapter.xhtml" media-type="text/plain"/>',
        '<itemref idref="chapter"/>',
    )
    entries = _replace_entry_data(_fixture_entries(), "EPUB/package.opf", package)

    with pytest.raises(EpubUnsupportedFeatureError, match="spine item is not XHTML"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_remote_manifest_target_is_rejected(tmp_path: Path) -> None:
    package = _package_xml(
        '<item id="chapter" href="https://example.invalid/chapter.xhtml" '
        'media-type="application/xhtml+xml"/>',
        '<itemref idref="chapter"/>',
    )
    entries = _replace_entry_data(_fixture_entries(), "EPUB/package.opf", package)

    with pytest.raises(EpubUnsupportedFeatureError, match="remote EPUB manifest"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_unsupported_package_version_is_rejected(tmp_path: Path) -> None:
    package = _package_xml(
        '<item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>',
        '<itemref idref="chapter"/>',
    ).replace(b'version="3.0"', b'version="4.0"')
    entries = _replace_entry_data(_fixture_entries(), "EPUB/package.opf", package)

    with pytest.raises(EpubUnsupportedFeatureError, match="package version"):
        _parse_artifact(_write_epub(tmp_path, entries))


@pytest.mark.parametrize("missing_element", ["metadata", "manifest", "spine"])
def test_missing_required_package_element_is_rejected(
    tmp_path: Path,
    missing_element: str,
) -> None:
    package = _package_xml(
        '<item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>',
        '<itemref idref="chapter"/>',
        include=missing_element,
    )
    entries = _replace_entry_data(_fixture_entries(), "EPUB/package.opf", package)

    with pytest.raises(EpubValidationError, match=f"exactly one {missing_element}"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_foreign_namespace_cannot_supply_required_opf_manifest(tmp_path: Path) -> None:
    package = _package_xml(
        '<item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>',
        '<itemref idref="chapter"/>',
    ).replace(b"<manifest>", b'<manifest xmlns="urn:foreign">')
    entries = _replace_entry_data(_fixture_entries(), "EPUB/package.opf", package)

    with pytest.raises(EpubValidationError, match="exactly one manifest"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_multi_spine_order_and_document_order_are_preserved() -> None:
    parsed = _parse_artifact(FIXTURES / "multi_spine.epub")

    assert [document.spine_index for document in parsed.spine_documents] == [0, 1]
    assert [document.href for document in parsed.spine_documents] == [
        "EPUB/first.xhtml",
        "EPUB/second.xhtml",
    ]
    assert [document.document_title for document in parsed.spine_documents] == [
        "First Invented Document",
        "Second Invented Document",
    ]
    assert [block.ordinal for block in parsed.spine_documents[1].blocks] == list(range(6))


def test_heading_paragraph_and_inline_text_are_extracted_without_rewriting() -> None:
    first = _parse_artifact(FIXTURES / "multi_spine.epub").spine_documents[0]

    assert [(block.kind, block.original_tag) for block in first.blocks] == [
        ("heading", "h1"),
        ("paragraph", "p"),
    ]
    assert first.blocks[1].normalized_text == ("Unicode “quotation” — with inline order preserved.")


def test_nested_list_blocks_do_not_duplicate_descendant_paragraphs() -> None:
    second = _parse_artifact(FIXTURES / "multi_spine.epub").spine_documents[1]
    list_blocks = [block for block in second.blocks if block.kind == "list_item"]

    assert [block.normalized_text for block in list_blocks] == [
        "Outer item — invented.",
        "Inner item “quoted”.",
    ]
    assert all(block.kind != "paragraph" for block in second.blocks)


def test_table_cells_do_not_duplicate_descendant_paragraphs() -> None:
    second = _parse_artifact(FIXTURES / "multi_spine.epub").spine_documents[1]
    table_blocks = [
        block for block in second.blocks if block.kind in {"caption", "table_header", "table_cell"}
    ]

    assert [(block.kind, block.normalized_text) for block in table_blocks] == [
        ("caption", "Invented table"),
        ("table_header", "Heading cell"),
        ("table_cell", "Data cell 42."),
    ]


def test_class_tokens_epub_type_and_language_are_preserved() -> None:
    parsed = _parse_artifact(FIXTURES / "multi_spine.epub")
    first_heading = parsed.spine_documents[0].blocks[0]
    second_heading = parsed.spine_documents[1].blocks[0]
    table_cell = parsed.spine_documents[1].blocks[-1]

    assert first_heading.class_names == ("primary", "lead")
    assert second_heading.class_names == ("secondary", "heading")
    assert second_heading.epub_type == "chapter"
    assert table_cell.class_names == ("numeric", "sample")
    assert all(
        block.language == "en-AU"
        for document in parsed.spine_documents
        for block in document.blocks
    )


def test_unicode_punctuation_is_preserved_exactly() -> None:
    parsed = _parse_artifact(FIXTURES / "multi_spine.epub")
    emitted_text = [
        block.normalized_text for document in parsed.spine_documents for block in document.blocks
    ]

    assert "Unicode “quotation” — with inline order preserved." in emitted_text
    assert "Inner item “quoted”." in emitted_text


def test_locator_uses_element_id_when_present() -> None:
    block = _parse_artifact(FIXTURES / "multi_spine.epub").spine_documents[1].blocks[0]

    assert block.element_id == "second-heading"
    assert block.locator == "EPUB/second.xhtml#second-heading"


def test_locator_uses_structural_path_when_element_id_is_absent() -> None:
    parsed = _parse_artifact(FIXTURES / "multi_spine.epub")
    paragraph = parsed.spine_documents[0].blocks[1]
    table_cell = parsed.spine_documents[1].blocks[-1]

    assert paragraph.element_id is None
    assert paragraph.locator == "EPUB/first.xhtml#/html[1]/body[1]/p[1]"
    assert table_cell.locator == ("EPUB/second.xhtml#/html[1]/body[1]/table[1]/tr[1]/td[1]")


def test_xhtml_block_count_limit_is_enforced_across_spine_documents() -> None:
    with pytest.raises(EpubSecurityError, match="block-count"):
        _parse_artifact(FIXTURES / "multi_spine.epub", maximum_xhtml_block_count=7)


def test_text_character_limit_is_enforced_after_normalization() -> None:
    with pytest.raises(EpubSecurityError, match="character limit"):
        _parse_artifact(
            FIXTURES / "multi_spine.epub",
            maximum_text_characters_per_block=20,
        )


def test_repeated_parse_has_identical_model_serialization() -> None:
    first = _parse_artifact(FIXTURES / "multi_spine.epub")
    second = _parse_artifact(FIXTURES / "multi_spine.epub")

    assert first.model_dump_json() == second.model_dump_json()


def test_scripts_styles_comments_hidden_content_and_navigation_are_not_emitted() -> None:
    parsed = _parse_artifact(FIXTURES / "multi_spine.epub")
    serialized = parsed.model_dump_json()

    assert "forbidden_script_text" not in serialized
    assert "display: none" not in serialized
    assert "ignored comment" not in serialized
    assert "hidden_metadata_text" not in serialized
    assert "navigation_control_text" not in serialized


def test_substantive_blocks_in_generic_nav_are_preserved(tmp_path: Path) -> None:
    xhtml = (
        b'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Title</title></head>'
        b"<body><nav><h2>Substantive heading</h2><p>Substantive text.</p></nav>"
        b"</body></html>"
    )
    entries = _replace_entry_data(_fixture_entries(), "EPUB/chapter.xhtml", xhtml)

    parsed = _parse_artifact(_write_epub(tmp_path, entries))

    assert [block.normalized_text for block in parsed.spine_documents[0].blocks] == [
        "Substantive heading",
        "Substantive text.",
    ]


def test_foreign_namespace_block_names_are_not_emitted(tmp_path: Path) -> None:
    xhtml = (
        b'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:f="urn:foreign">'
        b"<head><title>Title</title></head><body><f:p>Foreign text.</f:p>"
        b"<p>XHTML text.</p></body></html>"
    )
    entries = _replace_entry_data(_fixture_entries(), "EPUB/chapter.xhtml", xhtml)

    parsed = _parse_artifact(_write_epub(tmp_path, entries))

    assert [block.normalized_text for block in parsed.spine_documents[0].blocks] == ["XHTML text."]


def test_deep_inline_tree_does_not_expose_recursion_error(tmp_path: Path) -> None:
    depth = 1_100
    nested = ("<span>" * depth) + "Deep text." + ("</span>" * depth)
    xhtml = (
        '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Title</title></head>'
        f"<body><p>{nested}</p></body></html>"
    ).encode()
    entries = _replace_entry_data(_fixture_entries(), "EPUB/chapter.xhtml", xhtml)

    parsed = _parse_artifact(_write_epub(tmp_path, entries))

    assert parsed.spine_documents[0].blocks[0].normalized_text == "Deep text."


def test_stdlib_recursion_error_is_translated_at_public_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def exhaust_parser_capacity(_data: bytes) -> ElementTree.Element:
        raise RecursionError("simulated parser recursion limit")

    monkeypatch.setattr(ElementTree, "fromstring", exhaust_parser_capacity)

    with pytest.raises(EpubSecurityError, match="nesting") as caught:
        _parse_artifact(FIXTURES / "minimal_valid.epub")

    assert isinstance(caught.value.__cause__, RecursionError)


def test_aria_hidden_inline_content_is_not_emitted(tmp_path: Path) -> None:
    xhtml = (
        b'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Title</title></head>'
        b'<body><p>Visible <span aria-hidden="true">hidden words</span> tail.</p>'
        b"</body></html>"
    )
    entries = _replace_entry_data(_fixture_entries(), "EPUB/chapter.xhtml", xhtml)

    parsed = _parse_artifact(_write_epub(tmp_path, entries))

    assert parsed.spine_documents[0].blocks[0].normalized_text == "Visible tail."


def test_duplicate_xhtml_ids_are_rejected_for_unambiguous_locators(tmp_path: Path) -> None:
    xhtml = (
        b'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Title</title></head>'
        b'<body><h1 id="duplicate">One</h1><p id="duplicate">Two</p></body></html>'
    )
    entries = _replace_entry_data(_fixture_entries(), "EPUB/chapter.xhtml", xhtml)

    with pytest.raises(EpubValidationError, match="element ID is duplicated"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_malformed_xhtml_does_not_expose_raw_elementtree_error(tmp_path: Path) -> None:
    entries = _replace_entry_data(
        _fixture_entries(),
        "EPUB/chapter.xhtml",
        b"<html>",
    )

    with pytest.raises(EpubValidationError) as caught:
        _parse_artifact(_write_epub(tmp_path, entries))

    assert isinstance(caught.value.__cause__, ElementTree.ParseError)


def test_non_xhtml_xml_root_is_rejected(tmp_path: Path) -> None:
    entries = _replace_entry_data(
        _fixture_entries(),
        "EPUB/chapter.xhtml",
        b'<html xmlns="https://example.invalid/not-xhtml"><body><p>text</p></body></html>',
    )

    with pytest.raises(EpubUnsupportedFeatureError, match="not XHTML"):
        _parse_artifact(_write_epub(tmp_path, entries))


def test_output_models_are_frozen_and_forbid_extra_fields() -> None:
    parsed = _parse_artifact(FIXTURES / "minimal_valid.epub")

    with pytest.raises(ValidationError):
        parsed.package_title = "changed"
    with pytest.raises(ValidationError):
        type(parsed).model_validate({**parsed.model_dump(), "arbitrary": "metadata"})
