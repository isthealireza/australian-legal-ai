"""Synchronous, read-only client for the selected Federal Register endpoints."""

import json
from types import TracebackType
from typing import Any, Self

import httpx
from pydantic import ValidationError

from .errors import (
    FederalRegisterRedirectError,
    FederalRegisterRequestError,
    FederalRegisterResponseError,
)
from .models import (
    DocumentListResponse,
    DocumentMetadata,
    TitleMetadata,
    VersionListResponse,
    VersionMetadata,
)

_BASE_URL = "https://api.prod.legislation.gov.au/v1/"
_APPROVED_HOST = "api.prod.legislation.gov.au"
_USER_AGENT = "australian-legal-ai-research-prototype/0.1"
_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
_MAX_METADATA_BYTES = 1_048_576


class FederalRegisterClient:
    """Thin contract module for bounded Federal Register discovery."""

    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        self._client = httpx.Client(
            base_url=_BASE_URL,
            headers={"Accept": "application/json", "User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
            follow_redirects=False,
            transport=transport,
            trust_env=False,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def get_title(self, title_id: str) -> TitleMetadata:
        """Return strictly validated metadata for one approved-format title ID."""

        validated_title_id = self._validate_identifier(title_id)
        payload = self._get_json(f"titles('{validated_title_id}')")
        try:
            title = TitleMetadata.model_validate(payload)
        except ValidationError as exc:
            raise FederalRegisterResponseError("title metadata failed validation") from exc
        if title.title_id != validated_title_id:
            raise FederalRegisterResponseError("title response identifier did not match request")
        return title

    def get_latest_registered_version(self, title_id: str) -> VersionMetadata:
        """Resolve the one version the upstream marks as latest registered."""

        validated_title_id = self._validate_identifier(title_id)
        payload = self._get_json(
            "versions",
            params={
                "$filter": f"titleId eq '{validated_title_id}' and isLatest eq true",
            },
        )
        try:
            response = VersionListResponse.model_validate(payload)
        except ValidationError as exc:
            raise FederalRegisterResponseError("version metadata failed validation") from exc
        if response.next_link is not None:
            raise FederalRegisterResponseError(
                "version metadata included an unsupported continuation link"
            )
        if len(response.value) != 1:
            raise FederalRegisterResponseError(
                "latest registered version query did not return exactly one result"
            )
        version = response.value[0]
        if version.title_id != validated_title_id:
            raise FederalRegisterResponseError("version response identifier did not match request")
        if not version.is_latest:
            raise FederalRegisterResponseError("version response was not marked latest")
        return version

    def list_documents(self, register_id: str) -> tuple[DocumentMetadata, ...]:
        """Return validated document renditions for one registered version."""

        validated_register_id = self._validate_identifier(register_id)
        payload = self._get_json(
            "documents",
            params={"$filter": f"registerId eq '{validated_register_id}'"},
        )
        try:
            response = DocumentListResponse.model_validate(payload)
        except ValidationError as exc:
            raise FederalRegisterResponseError("document metadata failed validation") from exc
        if response.next_link is not None:
            raise FederalRegisterResponseError(
                "document metadata included an unsupported continuation link"
            )
        if any(document.register_id != validated_register_id for document in response.value):
            raise FederalRegisterResponseError("document response identifier did not match request")
        return tuple(response.value)

    @staticmethod
    def _validate_identifier(identifier: str) -> str:
        if (
            not isinstance(identifier, str)
            or len(identifier) != 11
            or not identifier[0].isupper()
            or not identifier[1:5].isdigit()
            or not identifier[5].isupper()
            or not identifier[6:].isdigit()
            or not identifier.isascii()
        ):
            raise FederalRegisterRequestError("invalid Federal Register identifier")
        return identifier

    def _get_json(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        with self._client.stream("GET", path, params=params) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if location is None:
                    raise FederalRegisterRedirectError(
                        "Federal Register redirect had no destination"
                    )
                destination = response.url.join(location)
                if (
                    destination.scheme != "https"
                    or destination.host != _APPROVED_HOST
                    or destination.port not in (None, 443)
                ):
                    raise FederalRegisterRedirectError("non-approved redirect destination")
                raise FederalRegisterRedirectError("approved-host redirects are not followed")
            if not response.is_success:
                raise FederalRegisterResponseError(
                    f"Federal Register returned HTTP {response.status_code}"
                ) from None

            media_type = response.headers.get("content-type", "").partition(";")[0].strip().lower()
            if media_type != "application/json":
                raise FederalRegisterResponseError("unexpected Federal Register content type")

            content_length = response.headers.get("content-length")
            if content_length is not None:
                if not content_length.isascii() or not content_length.isdigit():
                    raise FederalRegisterResponseError("invalid Federal Register content length")
                declared_bytes = int(content_length)
                if declared_bytes < 0 or declared_bytes > _MAX_METADATA_BYTES:
                    raise FederalRegisterResponseError(
                        "Federal Register metadata exceeded size limit"
                    )

            body = bytearray()
            for chunk in response.iter_bytes():
                if len(body) + len(chunk) > _MAX_METADATA_BYTES:
                    raise FederalRegisterResponseError(
                        "Federal Register metadata exceeded size limit"
                    )
                body.extend(chunk)

        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FederalRegisterResponseError("Federal Register returned malformed JSON") from exc
        if not isinstance(payload, dict):
            raise FederalRegisterResponseError("Federal Register JSON root was not an object")
        return payload
