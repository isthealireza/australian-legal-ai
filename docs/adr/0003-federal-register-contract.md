# ADR 0003: Federal Register contract boundary

- Status: Accepted
- Date: 2026-07-21

## Context

Sprint 1.1 needs a small, typed seam to the official Commonwealth Federal
Register of Legislation without introducing persistence, parsing, retrieval, or
legal-answering behaviour. The upstream API is live and unauthenticated, but its
published contract is permissive and may change.

Discovery used only HTTPS `GET` and `HEAD` requests to
`api.prod.legislation.gov.au` and `legislation.gov.au`. Automated tests do not
contact either host.

## Official contract observed

The complete OpenAPI document was inspected but is not committed:

- URL: `https://api.prod.legislation.gov.au/swagger/v1/swagger.json`
- OpenAPI version: 3.0.1
- API title and version: `Legislation Public API`, `v1`
- Retrieval time: `2026-07-20T16:48:06.2451529+00:00`
- Exact response-body SHA-256:
  `82946eeb6d54b9bf9b1f588af3d4aa481db93b6c1a1b45f426a020b133d29e8a`
- Observed deployment header:
  `X-Frl-Version: 2026.07.05-release.1+8e129750b1c91e94b9adaab7d475fb578bca2482`

The selected read-only endpoints are:

1. `GET /v1/titles('{title_id}')`, with the stable title ID as the path key.
2. `GET /v1/versions`, with
   `$filter=titleId eq '{title_id}' and isLatest eq true`.
3. `GET /v1/documents`, with
   `$filter=registerId eq '{register_id}'`.

The OpenAPI document declares `application/json` for these metadata responses.
The live responses used
`application/json; odata.metadata=minimal; odata.streaming=true; charset=utf-8`.
The OpenAPI document separately advertises `application/octet-stream` and
`application/json` for document-download operations; those operations are
outside this client.

No `ETag`, `Last-Modified`, `Content-Length`, `Content-Digest`, or
`Repr-Digest` header was observed on the successful selected metadata requests.
Responses used chunked transfer encoding. A `HEAD` probe to a document-download
operation returned `405 Method Not Allowed` with `Allow: GET`, so document
metadata, manifests, and later stored hashes must carry provenance rather than
assuming validators are available.

## Pilot observations

The Privacy Act 1988 title `C2004A03712` resolved to latest registered version
`C2026C00227`, compilation 104, starting 2026-06-04 and registered
2026-06-17. The API returned Word, authorised PDF, and EPUB primary renditions,
each as a single-volume document.

The Competition and Consumer Act 2010 title `C2004A00109` resolved to latest
registered version `C2026C00206`, compilation 164, starting 2026-05-27 and
registered 2026-05-28. The API returned four Word volumes, four authorised PDF
volumes, and one EPUB rendition. The multi-volume metadata and the Act's
schedule structure, including Schedule 2, are parser boundary cases deferred
from this task.

`isLatest` does not mean `isCurrent`: the Competition Act response was
`isLatest=true` and `isCurrent=false`, with an end date of 2026-07-01, while
the title reported commenced unincorporated amendments. The interface therefore
uses the term "latest registered version" and never labels that response
"current".

## Decision

Implement a thin hand-written synchronous HTTPX client under
`legal_ai.sources.frl`. Its interface exposes only title metadata, latest
registered version metadata, and document metadata for a returned register ID.
The base URL is fixed to
`https://api.prod.legislation.gov.au/v1/`; callers cannot supply a host.

The client uses an explicit prototype User-Agent and explicit connect, read,
write, and pool timeouts. It performs no retries, concurrency, async work,
authentication, or non-GET runtime requests. Redirect following is disabled.
Redirect destinations are parsed and checked against the exact approved HTTPS
host before every redirect is refused fail-closed. Metadata bodies are streamed
through a 1 MiB hard limit before JSON parsing.

Selected collection envelopes explicitly model `@odata.nextLink`. A non-null
continuation link is not followed and prevents any partial version or document
result from being returned. Pagination remains outside Sprint 1.1.

A generated OpenAPI client was rejected because it would expose unrelated
write, user, session, feedback, and document-content operations and make the
local interface track a large unstable schema. The hand-written module models
only fields essential to the selected provenance contract.

Synchronous HTTP is used because Sprint 1 performs bounded sequential source
discovery. Async or concurrent fetching would add interface and operational
complexity without a demonstrated requirement.

## Schema compatibility policy

Required provenance fields are present and strictly typed locally even though
the upstream OpenAPI component schemas declare no required fields. Missing
fields and incompatible types fail closed. Unknown additive fields are allowed
so unrelated upstream additions do not break the client. Title and register
identifiers are pattern-checked and preserved exactly, then compared with the
request to detect cross-response contamination.

The transport models preserve every upstream temporal string exactly, including
all fractional-second digits and any explicit `Z` or numeric offset.
Timezone-less values have unknown timezone semantics; the contract layer does
not infer or assign a timezone. Legal or effective-time normalization is
deferred to a later bounded domain layer and cannot change the authoritative
transport value used for serialization or hashing.

## Fixtures and contract tests

Six immutable, body-only JSON fixtures record title, latest registered version,
and document metadata for both pilot titles. Each has an adjacent manifest with
the official request, retrieval time, HTTP status, content type, observed
validator headers, SHA-256 of the exact checked-in fixture bytes, title ID,
register ID, and compilation number.

The checked-in body-only JSON text files have one terminal LF, which is included
in the manifest hash. Contract tests hash the bytes directly without parsing,
normalizing, or reserializing them.

Contract tests replay these fixtures through HTTPX `MockTransport` and the
public client interface. Normal tests have no live-network path and require no
HTTP mocking dependency beyond HTTPX.

## Network policy

The application client is restricted to the fixed Federal Register API host and
read-only `GET` operations. Manual discovery and fixture capture additionally
allowed `HEAD` and the official `legislation.gov.au` site. No API keys,
authentication, third-party mirrors, search engines, broad crawling, or bulk
concurrent downloads are used.

The separately approved PyPI exception is build-time only for `uv lock` and
`uv sync`; it does not expand this runtime decision.

## Consequences and deferred work

The upstream remains changeable. Known risks include case-duplicated OpenAPI
paths, component schemas with no required fields, timezone-less date-times,
`$expand=documents` being rejected despite document relationships in the
schema, absent cache/integrity validators, and divergence between latest
registered and current law.

This bounded adapter does not create the future audit store. Before any
application workflow performs automatic L0 retrieval, its integration must
provide the fail-closed audit sink required by the root constitution. The
recorded-fixture test path performs no live retrieval.

Sprint 1.2 will decide and implement immutable raw artifact capture,
content-addressed storage, download limits for full legislation artifacts, and
authorised PDF retention. The authorised PDF will be retained as an immutable
provenance artifact while the most structured official rendition available is
used for parsing.

Sprint 1.3 will implement secure legislative parsing and hierarchy preservation,
including multi-volume documents and schedule boundaries. No storage or parser
interface is introduced by this decision.
