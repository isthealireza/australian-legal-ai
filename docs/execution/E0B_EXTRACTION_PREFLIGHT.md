# E0-B Extraction Preflight

This checklist is the safety boundary for turning a staged WALW PDF into
answerable corpus records. It does not activate a source and it does not
change the existing MVP answer path.

## Required deterministic pipeline

1. Verify the exact PDF SHA-256 against its manifest before parsing.
2. Extract text with a pinned, reproducible tool and fixed options
   (`pdftotext -layout` or an explicitly versioned equivalent).
3. Preserve page boundaries and statutory hierarchy; do not infer missing
   regulation numbers from model output.
4. Parse only records whose identifier and boundaries are recognized by the
   deterministic parser. Ambiguous or malformed boundaries become refusals.
5. Store each record's exact text digest and bind the companion sections file
   to the parent source id and PDF digest.
6. Run byte-level quote checks, duplicate/ambiguity checks, and the existing
   ss 55–56 golden suite.

## Activation gate

The extracted records remain staging-only until all of these are true:

- source/version and currency are accepted by the owner;
- a human compares representative pages and every parser exception is
  accounted for;
- the complete targeted and repository-authoritative test suites pass;
- out-of-corpus and unsupported pinpoint queries still refuse;
- a rollback consists of removing the staged fixture, with no migration.

No provider call, browser automation, generated legal text, or secret is
permitted in this task.
