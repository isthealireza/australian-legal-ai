# ADR 0001: Product purpose

- Status: Accepted
- Date: 2026-07-20

## Context

The project needs a clear current purpose and boundary before implementation
begins. Its present controls and validation are not suitable for production use
or decisions affecting legal rights.

## Decision

The current purpose is a portfolio-quality internal prototype for Alirad. It may
support learning and preliminary review using synthetic or public data, but it
must not make final legal decisions and must not use real client data.

A commercial product is deferred behind a separate legal, privacy, and security
gate. That gate requires appropriate legal review, privacy assessment, provider
due diligence, access controls, incident planning, and security testing before
commercial use is considered.

## Consequences

Sprint work must remain within the prototype boundary. Any proposed commercial
or production use requires a separate decision and evidence that the legal,
privacy, and security gate has been satisfied.
