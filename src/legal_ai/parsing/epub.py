"""Read-only, bounded EPUB container and XHTML structural extraction."""

import hashlib
import ntpath
import posixpath
import re
import stat
import unicodedata
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

from .errors import (
    EpubParseError,
    EpubSecurityError,
    EpubUnsupportedFeatureError,
    EpubValidationError,
)
from .models import (
    EpubBlockKind,
    EpubParseLimits,
    EpubSpineDocument,
    EpubTextBlock,
    ParsedEpubDocument,
)

_READ_CHUNK_SIZE = 64 * 1024
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_EPUB_MIMETYPE = b"application/epub+zip"
_CONTAINER_ENTRY = "META-INF/container.xml"
_CONTAINER_NAMESPACE = "urn:oasis:names:tc:opendocument:xmlns:container"
_OPF_NAMESPACE = "http://www.idpf.org/2007/opf"
_OPF_MEDIA_TYPE = "application/oebps-package+xml"
_XHTML_NAMESPACE = "http://www.w3.org/1999/xhtml"
_XHTML_MEDIA_TYPE = "application/xhtml+xml"
_DC_NAMESPACE = "http://purl.org/dc/elements/1.1/"
_EPUB_NAMESPACE = "http://www.idpf.org/2007/ops"
_XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
_SUPPORTED_COMPRESSION = frozenset({zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED})
_XML_DECLARATION = re.compile(r"^\s*<\?xml\b.*?\?>", re.IGNORECASE | re.DOTALL)
_XML_ENCODING = re.compile(
    r"\bencoding\s*=\s*(['\"])(?P<encoding>[^'\"]+)\1",
    re.IGNORECASE,
)
_FORBIDDEN_XML_DECLARATION = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)
_EXTERNAL_IDENTIFIER = re.compile(
    r"<![^>]*\b(?:SYSTEM|PUBLIC)\b",
    re.IGNORECASE | re.DOTALL,
)
_PROCESSING_INSTRUCTION = re.compile(r"<\?", re.IGNORECASE)
_BLOCK_KINDS: dict[str, EpubBlockKind] = {
    "h1": "heading",
    "h2": "heading",
    "h3": "heading",
    "h4": "heading",
    "h5": "heading",
    "h6": "heading",
    "p": "paragraph",
    "li": "list_item",
    "dt": "definition_term",
    "dd": "definition_description",
    "blockquote": "blockquote",
    "pre": "preformatted",
    "caption": "caption",
    "th": "table_header",
    "td": "table_cell",
}
_OWNED_DESCENDANT_BLOCKS: dict[str, frozenset[str]] = {
    "li": frozenset({"p"}),
    "dt": frozenset({"p"}),
    "dd": frozenset({"p"}),
    "blockquote": frozenset({"p"}),
    "caption": frozenset({"p"}),
    "th": frozenset({"p"}),
    "td": frozenset({"p"}),
}
_IGNORED_SUBTREES = frozenset({"head", "script", "style", "noscript", "template"})
_NAVIGATION_TYPES = frozenset({"toc", "landmarks", "page-list", "lot", "loi"})


@dataclass(frozen=True, slots=True)
class _ManifestItem:
    identifier: str
    href: str
    media_type: str


@dataclass(frozen=True, slots=True)
class _Package:
    identifier: str | None
    title: str | None
    language: str | None
    spine_items: tuple[_ManifestItem, ...]


class _ArchiveReader:
    def __init__(
        self,
        archive: zipfile.ZipFile,
        limits: EpubParseLimits,
        entries: Sequence[zipfile.ZipInfo],
    ) -> None:
        self._archive = archive
        self._limits = limits
        self._entries: dict[str, zipfile.ZipInfo] = {}
        self._validate_directory(entries)

    def _validate_directory(self, entries: Sequence[zipfile.ZipInfo]) -> None:
        if len(entries) > self._limits.maximum_entry_count:
            raise EpubSecurityError("EPUB ZIP entry-count limit exceeded")
        if not entries:
            raise EpubValidationError("EPUB ZIP contains no entries")

        total_uncompressed = 0
        for entry in entries:
            normalized_name = _validate_entry_name(entry.orig_filename)
            if normalized_name in self._entries:
                raise EpubSecurityError(
                    f"EPUB ZIP contains duplicate normalized entry: {normalized_name}"
                )
            if entry.flag_bits & 0x1:
                raise EpubUnsupportedFeatureError(
                    f"encrypted EPUB ZIP entry is unsupported: {normalized_name}"
                )
            if entry.compress_type not in _SUPPORTED_COMPRESSION:
                raise EpubUnsupportedFeatureError(
                    f"unsupported EPUB ZIP compression for entry: {normalized_name}"
                )
            _validate_entry_file_type(entry, normalized_name)
            if entry.file_size > self._limits.maximum_entry_uncompressed_bytes:
                raise EpubSecurityError(
                    f"EPUB ZIP per-entry uncompressed limit exceeded: {normalized_name}"
                )
            total_uncompressed += entry.file_size
            if total_uncompressed > self._limits.maximum_total_uncompressed_bytes:
                raise EpubSecurityError("EPUB ZIP total uncompressed limit exceeded")
            ratio = _compression_ratio(entry)
            if ratio > self._limits.maximum_compression_ratio:
                raise EpubSecurityError(
                    f"EPUB ZIP compression-ratio limit exceeded: {normalized_name}"
                )
            self._entries[normalized_name] = entry

        first = entries[0]
        if _validate_entry_name(first.filename) != "mimetype":
            raise EpubValidationError("EPUB mimetype entry must be first")
        if first.compress_type != zipfile.ZIP_STORED:
            raise EpubValidationError("EPUB mimetype entry must be stored without compression")
        if self.read("mimetype") != _EPUB_MIMETYPE:
            raise EpubValidationError("EPUB mimetype entry is incorrect")

    def contains(self, name: str) -> bool:
        return name in self._entries

    def read(self, name: str) -> bytes:
        entry = self._entries.get(name)
        if entry is None:
            raise EpubValidationError(f"required EPUB entry is missing: {name}")

        chunks: list[bytes] = []
        byte_count = 0
        with self._archive.open(entry, mode="r") as source:
            while chunk := source.read(_READ_CHUNK_SIZE):
                byte_count += len(chunk)
                if byte_count > self._limits.maximum_entry_uncompressed_bytes:
                    raise EpubSecurityError(f"EPUB entry expanded beyond its byte limit: {name}")
                chunks.append(chunk)
        if byte_count != entry.file_size:
            raise EpubValidationError(f"EPUB entry size did not match ZIP metadata: {name}")
        return b"".join(chunks)


def parse_epub(
    artifact_path: Path,
    *,
    expected_sha256: str,
    limits: EpubParseLimits,
) -> ParsedEpubDocument:
    """Verify and parse one immutable EPUB artifact without extracting it to disk."""

    try:
        artifact_sha256 = _verify_artifact(artifact_path, expected_sha256, limits)
        with zipfile.ZipFile(artifact_path, mode="r") as archive:
            entries = archive.infolist()
            if len(entries) > limits.maximum_entry_count:
                raise EpubSecurityError("EPUB ZIP entry-count limit exceeded")
            _validate_raw_entry_names(artifact_path, entries)
            reader = _ArchiveReader(archive, limits, entries)
            package_path = _discover_package(reader)
            package = _parse_package(reader, package_path)
            documents: list[EpubSpineDocument] = []
            total_blocks = 0
            for spine_index, item in enumerate(package.spine_items):
                document, total_blocks = _parse_spine_document(
                    reader,
                    item,
                    spine_index,
                    total_blocks,
                    limits,
                )
                documents.append(document)
        return ParsedEpubDocument(
            artifact_sha256=artifact_sha256,
            package_identifier=package.identifier,
            package_title=package.title,
            language=package.language,
            spine_documents=tuple(documents),
        )
    except EpubParseError:
        raise
    except zipfile.BadZipFile as exc:
        raise EpubValidationError("artifact is not a valid EPUB ZIP container") from exc
    except RecursionError as exc:
        raise EpubSecurityError("EPUB XML nesting exceeded safe parser capacity") from exc
    except (RuntimeError, NotImplementedError) as exc:
        raise EpubUnsupportedFeatureError("EPUB uses an unsupported ZIP feature") from exc
    except (ElementTree.ParseError, UnicodeError, KeyError, ValueError) as exc:
        raise EpubValidationError("EPUB required structure could not be parsed safely") from exc
    except OSError as exc:
        raise EpubParseError("EPUB artifact could not be read safely") from exc


def _verify_artifact(
    artifact_path: Path,
    expected_sha256: str,
    limits: EpubParseLimits,
) -> str:
    if not isinstance(artifact_path, Path):
        raise EpubValidationError("EPUB artifact input must be a filesystem Path")
    if not isinstance(expected_sha256, str) or _SHA256_PATTERN.fullmatch(expected_sha256) is None:
        raise EpubValidationError("expected SHA-256 must be 64 lowercase hexadecimal characters")

    artifact_stat = artifact_path.lstat()
    if stat.S_ISLNK(artifact_stat.st_mode):
        raise EpubSecurityError("EPUB artifact source must not be a symlink")
    if not stat.S_ISREG(artifact_stat.st_mode):
        raise EpubValidationError("EPUB artifact source must be a regular file")
    if artifact_stat.st_size == 0:
        raise EpubValidationError("EPUB artifact must not be empty")
    if artifact_stat.st_size > limits.maximum_archive_bytes:
        raise EpubSecurityError("EPUB archive byte-size limit exceeded")

    digest = hashlib.sha256()
    byte_count = 0
    with artifact_path.open("rb") as source:
        while chunk := source.read(_READ_CHUNK_SIZE):
            byte_count += len(chunk)
            if byte_count > limits.maximum_archive_bytes:
                raise EpubSecurityError("EPUB archive byte-size limit exceeded while hashing")
            digest.update(chunk)
    if byte_count == 0:
        raise EpubValidationError("EPUB artifact must not be empty")
    actual_sha256 = digest.hexdigest()
    if actual_sha256 != expected_sha256:
        raise EpubValidationError("EPUB artifact SHA-256 did not match the expected value")
    return actual_sha256


def _validate_raw_entry_names(
    artifact_path: Path,
    entries: Sequence[zipfile.ZipInfo],
) -> None:
    with artifact_path.open("rb") as source:
        for entry in entries:
            source.seek(entry.header_offset)
            header = source.read(30)
            if len(header) != 30 or header[:4] != b"PK\x03\x04":
                raise EpubValidationError("EPUB ZIP local entry header is malformed")
            local_flags = int.from_bytes(header[6:8], "little")
            if local_flags & 0x1:
                raise EpubUnsupportedFeatureError(
                    f"encrypted EPUB ZIP entry is unsupported: {entry.orig_filename}"
                )
            name_length = int.from_bytes(header[26:28], "little")
            raw_name = source.read(name_length)
            if len(raw_name) != name_length:
                raise EpubValidationError("EPUB ZIP local entry name is truncated")
            encoding = "utf-8" if local_flags & 0x800 else "cp437"
            local_name = raw_name.decode(encoding)
            _validate_entry_name(local_name)
            if local_name != entry.orig_filename:
                raise EpubValidationError(
                    f"EPUB ZIP local and central entry names differ: {entry.orig_filename}"
                )


def _validate_entry_name(name: str) -> str:
    if not name:
        raise EpubSecurityError("EPUB ZIP entry name must not be empty")
    if "\\" in name:
        raise EpubSecurityError(f"EPUB ZIP entry uses ambiguous backslashes: {name}")
    if any(ord(character) < 32 for character in name):
        raise EpubSecurityError("EPUB ZIP entry name contains a control character")
    drive, _tail = ntpath.splitdrive(name)
    if drive or name.startswith("/") or name.startswith("//"):
        raise EpubSecurityError(f"EPUB ZIP entry path must be relative: {name}")
    components = name.split("/")
    if any(component in {"", ".", ".."} for component in components):
        raise EpubSecurityError(f"EPUB ZIP entry path has an unsafe component: {name}")
    normalized = unicodedata.normalize("NFC", posixpath.normpath(name))
    if normalized in {"", ".", ".."} or normalized.startswith("../"):
        raise EpubSecurityError(f"EPUB ZIP entry path escapes the archive: {name}")
    return normalized


def _validate_entry_file_type(entry: zipfile.ZipInfo, name: str) -> None:
    if entry.create_system != 3:
        return
    unix_mode = entry.external_attr >> 16
    file_type = stat.S_IFMT(unix_mode)
    if file_type == stat.S_IFLNK:
        raise EpubSecurityError(f"EPUB ZIP symlink entry is forbidden: {name}")
    if file_type not in {0, stat.S_IFREG}:
        raise EpubUnsupportedFeatureError(f"EPUB ZIP special-file entry is unsupported: {name}")


def _compression_ratio(entry: zipfile.ZipInfo) -> float:
    if entry.file_size == 0:
        return 0.0
    if entry.compress_size == 0:
        return float("inf")
    return entry.file_size / entry.compress_size


def _discover_package(reader: _ArchiveReader) -> str:
    container = _parse_xml(reader.read(_CONTAINER_ENTRY), _CONTAINER_ENTRY)
    if container.tag != f"{{{_CONTAINER_NAMESPACE}}}container":
        raise EpubValidationError("EPUB container.xml has an unsupported root element")
    if container.get("version") != "1.0":
        raise EpubUnsupportedFeatureError("EPUB container version is unsupported")
    usable_rootfiles: list[str] = []
    for element in container.iter(f"{{{_CONTAINER_NAMESPACE}}}rootfile"):
        if element.get("media-type") == _OPF_MEDIA_TYPE and element.get("full-path"):
            usable_rootfiles.append(_resolve_reference(None, element.get("full-path", "")))
    if len(usable_rootfiles) != 1:
        raise EpubValidationError("EPUB container must declare exactly one usable rootfile")
    package_path = usable_rootfiles[0]
    if not reader.contains(package_path):
        raise EpubValidationError(f"EPUB package rootfile is missing: {package_path}")
    return package_path


def _parse_package(reader: _ArchiveReader, package_path: str) -> _Package:
    root = _parse_xml(reader.read(package_path), package_path)
    if root.tag != f"{{{_OPF_NAMESPACE}}}package":
        raise EpubValidationError(f"EPUB package has an unsupported root element: {package_path}")
    if root.get("version") != "3.0":
        raise EpubUnsupportedFeatureError("EPUB package version is unsupported")

    metadata = _require_single_child(root, "metadata", package_path)
    manifest = _require_single_child(root, "manifest", package_path)
    spine = _require_single_child(root, "spine", package_path)
    package_identifier = _package_identifier(root, metadata)
    package_title = _first_metadata_text(metadata, "title")
    language = _first_metadata_text(metadata, "language")

    manifest_items: dict[str, _ManifestItem] = {}
    for element in _element_children(manifest, "item"):
        identifier = element.get("id", "")
        href = element.get("href", "")
        media_type = element.get("media-type", "")
        if not identifier or not href or not media_type:
            raise EpubValidationError(f"EPUB manifest item is incomplete: {package_path}")
        if identifier in manifest_items:
            raise EpubValidationError(f"EPUB manifest ID is duplicated: {identifier}")
        resolved_href = _resolve_reference(package_path, href)
        if not reader.contains(resolved_href):
            raise EpubValidationError(f"EPUB manifest target is missing: {resolved_href}")
        manifest_items[identifier] = _ManifestItem(
            identifier=identifier,
            href=resolved_href,
            media_type=media_type,
        )

    spine_items: list[_ManifestItem] = []
    seen_references: set[str] = set()
    for element in _element_children(spine, "itemref"):
        reference = element.get("idref", "")
        if not reference:
            raise EpubValidationError(f"EPUB spine item is missing idref: {package_path}")
        if reference in seen_references:
            raise EpubValidationError(f"EPUB spine reference is duplicated: {reference}")
        seen_references.add(reference)
        item = manifest_items.get(reference)
        if item is None:
            raise EpubValidationError(f"EPUB spine references a missing manifest ID: {reference}")
        if item.media_type != _XHTML_MEDIA_TYPE:
            raise EpubUnsupportedFeatureError(f"EPUB spine item is not XHTML: {item.href}")
        spine_items.append(item)
    if not spine_items:
        raise EpubValidationError("EPUB package spine must contain at least one XHTML item")
    return _Package(
        identifier=package_identifier,
        title=package_title,
        language=language,
        spine_items=tuple(spine_items),
    )


def _require_single_child(
    parent: ElementTree.Element,
    local_name: str,
    entry_name: str,
) -> ElementTree.Element:
    children = list(_element_children(parent, local_name))
    if len(children) != 1:
        raise EpubValidationError(
            f"EPUB package requires exactly one {local_name} element: {entry_name}"
        )
    return children[0]


def _element_children(
    parent: ElementTree.Element,
    local_name: str,
) -> list[ElementTree.Element]:
    return [child for child in parent if child.tag == f"{{{_OPF_NAMESPACE}}}{local_name}"]


def _package_identifier(
    package: ElementTree.Element,
    metadata: ElementTree.Element,
) -> str | None:
    identifiers = list(metadata.iter(f"{{{_DC_NAMESPACE}}}identifier"))
    unique_identifier = package.get("unique-identifier")
    if unique_identifier:
        for identifier in identifiers:
            if identifier.get("id") == unique_identifier:
                return _optional_normalized_text(identifier)
    if identifiers:
        return _optional_normalized_text(identifiers[0])
    return None


def _first_metadata_text(metadata: ElementTree.Element, local_name: str) -> str | None:
    elements = list(metadata.iter(f"{{{_DC_NAMESPACE}}}{local_name}"))
    return _optional_normalized_text(elements[0]) if elements else None


def _resolve_reference(owner: str | None, reference: str) -> str:
    if not reference or "\\" in reference:
        raise EpubSecurityError("EPUB internal reference is empty or ambiguous")
    parsed = urlsplit(reference)
    if parsed.scheme or parsed.netloc:
        raise EpubUnsupportedFeatureError(
            f"remote EPUB manifest reference is unsupported: {reference}"
        )
    if parsed.query or parsed.fragment:
        raise EpubUnsupportedFeatureError(
            f"EPUB internal reference query or fragment is unsupported: {reference}"
        )
    decoded_path = unquote(parsed.path)
    if not decoded_path or "\\" in decoded_path:
        raise EpubSecurityError("EPUB internal reference is empty or ambiguous")
    drive, _tail = ntpath.splitdrive(decoded_path)
    components = decoded_path.split("/")
    if (
        drive
        or decoded_path.startswith("/")
        or any(component in {"", ".", ".."} for component in components)
    ):
        raise EpubSecurityError(f"EPUB internal reference is unsafe: {reference}")
    base = posixpath.dirname(owner) if owner is not None else ""
    resolved = unicodedata.normalize("NFC", posixpath.normpath(posixpath.join(base, decoded_path)))
    if resolved in {"", ".", ".."} or resolved.startswith("../"):
        raise EpubSecurityError(f"EPUB internal reference escapes the archive: {reference}")
    return resolved


def _parse_xml(data: bytes, entry_name: str) -> ElementTree.Element:
    try:
        decoded = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise EpubUnsupportedFeatureError(
            f"EPUB XML encoding is unsupported; UTF-8 is required: {entry_name}"
        ) from exc
    declaration = _XML_DECLARATION.match(decoded)
    if declaration is not None:
        encoding = _XML_ENCODING.search(declaration.group())
        if encoding is not None and encoding.group("encoding").casefold() not in {
            "utf-8",
            "utf8",
        }:
            raise EpubUnsupportedFeatureError(
                f"EPUB XML encoding is unsupported; UTF-8 is required: {entry_name}"
            )
    if _FORBIDDEN_XML_DECLARATION.search(decoded) or _EXTERNAL_IDENTIFIER.search(decoded):
        raise EpubSecurityError(f"EPUB XML declarations are forbidden: {entry_name}")
    without_declaration = _XML_DECLARATION.sub("", decoded, count=1)
    if _PROCESSING_INSTRUCTION.search(without_declaration):
        raise EpubSecurityError(f"EPUB XML processing instructions are forbidden: {entry_name}")
    try:
        return ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise EpubValidationError(f"EPUB XML is malformed: {entry_name}") from exc


def _parse_spine_document(
    reader: _ArchiveReader,
    item: _ManifestItem,
    spine_index: int,
    prior_block_count: int,
    limits: EpubParseLimits,
) -> tuple[EpubSpineDocument, int]:
    root = _parse_xml(reader.read(item.href), item.href)
    if root.tag != f"{{{_XHTML_NAMESPACE}}}html":
        raise EpubUnsupportedFeatureError(f"EPUB spine document is not XHTML: {item.href}")

    parent_map = {child: parent for parent in root.iter() for child in parent}
    _validate_unique_element_ids(root, item.href)
    document_title = _document_title(root)
    blocks: list[EpubTextBlock] = []
    total_blocks = prior_block_count
    for element in root.iter():
        if (
            not isinstance(element.tag, str)
            or _namespace(element.tag) != _XHTML_NAMESPACE
            or _is_ignored(element, parent_map)
        ):
            continue
        local_name = _local_name(element.tag)
        kind = _BLOCK_KINDS.get(local_name)
        if kind is None or _is_owned_descendant(element, local_name, parent_map):
            continue
        normalized_text = _normalize_text(_owned_text(element, local_name))
        if not normalized_text:
            continue
        if len(normalized_text) > limits.maximum_text_characters_per_block:
            raise EpubSecurityError(f"EPUB XHTML text-block character limit exceeded: {item.href}")
        if total_blocks >= limits.maximum_xhtml_block_count:
            raise EpubSecurityError("EPUB XHTML block-count limit exceeded")
        element_id = element.get("id") or element.get(f"{{{_XML_NAMESPACE}}}id")
        locator = (
            f"{item.href}#{element_id}"
            if element_id
            else f"{item.href}#{_structural_path(element, parent_map)}"
        )
        blocks.append(
            EpubTextBlock(
                ordinal=len(blocks),
                kind=kind,
                original_tag=local_name,
                normalized_text=normalized_text,
                element_id=element_id,
                locator=locator,
                class_names=tuple(element.get("class", "").split()),
                epub_type=element.get(f"{{{_EPUB_NAMESPACE}}}type"),
                language=_inherited_language(element, parent_map),
            )
        )
        total_blocks += 1
    return (
        EpubSpineDocument(
            spine_index=spine_index,
            href=item.href,
            declared_media_type=item.media_type,
            document_title=document_title,
            blocks=tuple(blocks),
        ),
        total_blocks,
    )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _namespace(tag: str) -> str | None:
    if tag.startswith("{") and "}" in tag:
        return tag[1:].split("}", 1)[0]
    return None


def _document_title(root: ElementTree.Element) -> str | None:
    for element in root.iter():
        if (
            isinstance(element.tag, str)
            and _namespace(element.tag) == _XHTML_NAMESPACE
            and _local_name(element.tag) == "title"
        ):
            return _optional_normalized_text(element)
    return None


def _structural_path(
    element: ElementTree.Element,
    parent_map: dict[ElementTree.Element, ElementTree.Element],
) -> str:
    segments: list[str] = []
    current: ElementTree.Element | None = element
    while current is not None:
        name = _local_name(current.tag)
        sibling_index = 1
        parent = parent_map.get(current)
        if parent is not None:
            for sibling in parent:
                if sibling is current:
                    break
                if isinstance(sibling.tag, str) and _local_name(sibling.tag) == name:
                    sibling_index += 1
        segments.append(f"{name}[{sibling_index}]")
        current = parent
    return "/" + "/".join(reversed(segments))


def _is_ignored(
    element: ElementTree.Element,
    parent_map: dict[ElementTree.Element, ElementTree.Element],
) -> bool:
    current: ElementTree.Element | None = element
    while current is not None:
        if isinstance(current.tag, str) and _namespace(current.tag) == _XHTML_NAMESPACE:
            local_name = _local_name(current.tag)
            if local_name in _IGNORED_SUBTREES or (
                local_name == "nav" and _is_navigation_control(current)
            ):
                return True
        if _element_is_hidden(current):
            return True
        current = parent_map.get(current)
    return False


def _element_is_hidden(element: ElementTree.Element) -> bool:
    return "hidden" in element.attrib or element.get("aria-hidden", "").casefold() == "true"


def _is_navigation_control(element: ElementTree.Element) -> bool:
    epub_types = element.get(f"{{{_EPUB_NAMESPACE}}}type", "").split()
    return bool(_NAVIGATION_TYPES.intersection(epub_types)) or element.get("role") in {
        "doc-toc",
        "navigation",
    }


def _is_owned_descendant(
    element: ElementTree.Element,
    local_name: str,
    parent_map: dict[ElementTree.Element, ElementTree.Element],
) -> bool:
    current = parent_map.get(element)
    while current is not None:
        if isinstance(current.tag, str):
            owner_name = _local_name(current.tag)
            if _namespace(
                current.tag
            ) == _XHTML_NAMESPACE and local_name in _OWNED_DESCENDANT_BLOCKS.get(
                owner_name, frozenset()
            ):
                return True
        current = parent_map.get(current)
    return False


def _owned_text(element: ElementTree.Element, owner_name: str) -> str:
    fragments: list[str] = []
    stack: list[ElementTree.Element | str] = [element]
    while stack:
        current = stack.pop()
        if isinstance(current, str):
            fragments.append(current)
            continue
        if current.text:
            fragments.append(current.text)
        for child in reversed(current):
            child_name = _local_name(child.tag) if isinstance(child.tag, str) else ""
            if child.tail:
                stack.append(child.tail)
            is_xhtml = isinstance(child.tag, str) and _namespace(child.tag) == _XHTML_NAMESPACE
            ignored = is_xhtml and (
                child_name in _IGNORED_SUBTREES
                or (child_name == "nav" and _is_navigation_control(child))
            )
            separate_block = (
                is_xhtml
                and child_name in _BLOCK_KINDS
                and child_name not in _OWNED_DESCENDANT_BLOCKS.get(owner_name, frozenset())
            )
            if not ignored and not _element_is_hidden(child) and not separate_block:
                stack.append(child)
    return "".join(fragments)


def _validate_unique_element_ids(root: ElementTree.Element, entry_name: str) -> None:
    identifiers: set[str] = set()
    for element in root.iter():
        identifier = element.get("id") or element.get(f"{{{_XML_NAMESPACE}}}id")
        if identifier is None:
            continue
        if identifier in identifiers:
            raise EpubValidationError(f"EPUB XHTML element ID is duplicated: {entry_name}")
        identifiers.add(identifier)


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _optional_normalized_text(element: ElementTree.Element) -> str | None:
    normalized = _normalize_text("".join(element.itertext()))
    return normalized or None


def _inherited_language(
    element: ElementTree.Element,
    parent_map: dict[ElementTree.Element, ElementTree.Element],
) -> str | None:
    current: ElementTree.Element | None = element
    while current is not None:
        language = current.get(f"{{{_XML_NAMESPACE}}}lang") or current.get("lang")
        if language:
            return language
        current = parent_map.get(current)
    return None
