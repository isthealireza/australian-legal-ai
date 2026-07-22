# ADR 0004: Immutable provenance store

- Status: Accepted
- Date: 2026-07-22

## Context

Sprint 1.2 needs to retain exact Federal Register document bytes before later
download orchestration, parsing, publication, or retrieval exists. The byte
store and provenance database have different failure and transaction models,
so their ordering, identity, and residual cleanup behavior must be explicit.

## Decision

Use a synchronous local content-addressed filesystem store for raw artifact
bytes and PostgreSQL for structured artifact and source-document capture
metadata. SQLAlchemy Core, Psycopg 3, and explicit Alembic migrations are used;
ORM mappings and Sessions are not.

Artifact roots and maximum byte limits are injected by the caller. No
product-wide byte limit is selected here. The store streams bytes through
SHA-256 and publishes only non-empty artifacts at:

```text
sha256/<first-two-hex>/<next-two-hex>/<full-lowercase-sha256>.blob
```

The digest must be exactly 64 lowercase hexadecimal characters. Every key
component is generated internally from that digest. The relative key is
rejected unless its components exactly match the approved shape and contain no
absolute root, empty component, `.` or `..`. Caller filenames, URLs, titles,
register IDs, and document IDs never enter a filesystem path.

The configured root is created, resolved, and normalized once. A validated
relative key is joined beneath that root. Lexical containment comparison is
filesystem-independent during publication; on Windows it strips `\\?\` and
`\\?\UNC\` extended-length representations, normalizes separators, and compares
case-insensitively. This avoids the race where concurrent directory creation
caused `Path.resolve(strict=False)` to represent the same valid path differently.

## Immutable publication and errors

Bytes are written to a unique temporary file on the same filesystem, flushed,
closed, and then published with a hard link. Hard-link creation never
overwrites an existing destination. A successful link is verified from the
final path for exact size and SHA-256 before the publication is returned.

After any publication `OSError`, the store first determines whether the final
destination now exists. An existing final is verified and reused only when its
size and SHA-256 are exact; corrupt or mismatched bytes fail closed. If no final
exists, Windows access-denied, sharing-violation, and lock-violation errors may
be retried for at most three attempts with 10 milliseconds between attempts.
All other publication failures, and exhausted transient failures, become a
typed artifact publication error. Raw `OSError` and `PermissionError` values do
not escape the public store operation.

Temporary-file deletion uses the same bounded policy for known transient
Windows failures. Before verified publication, a persistent cleanup failure is
reported as a typed store error. After the final artifact is published and
verified, persistent temporary-file cleanup failure does not invalidate or
delete the final artifact and does not escape as a raw OS error. It may leave a
residual `.artifact-*.tmp` file. This sprint adds no cleanup daemon.

## Filesystem and database ordering

The immutable filesystem artifact is fully published and verified before the
repository begins its database transaction. The repository then inserts or
obtains the artifact metadata row and source-document capture row. Compatible
duplicate identities are idempotent; hash or critical-provenance conflicts fail
closed. No update or delete repository operation is exposed.

If database registration fails, the verified blob remains available for a
later retry. Likewise, when registration runs inside a caller-managed database
transaction, rolling back that outer transaction removes both the
`provenance_artifacts` and `source_document_captures` rows but intentionally
retains the already verified filesystem blob. Such a blob is unreferenced but
content-addressed. Automatic garbage collection is deferred.

## Consequences and residual limitations

The local filesystem is suitable for this bounded development foundation but
does not provide production object-storage availability, replication, access
control, or lifecycle management. File flushing does not imply durable parent
directory metadata across every crash or filesystem. The store therefore makes
no stronger crash-durability claim.

A continuously denied cleanup can leave a temporary file, and a database
failure or caller rollback can leave an unreferenced final blob. Neither case
triggers automatic deletion because deleting the wrong immutable artifact is a
greater integrity failure. Operators may inspect these residuals, but garbage
collection and cleanup automation require a later bounded decision.

Production object storage, document downloading, parsing, quarantine,
publication, retrieval, and legal-answering behavior remain deferred. No live
network access or parser is introduced by this decision.
