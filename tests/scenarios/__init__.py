"""Scenario test suite — offline, deterministic scenario tests for the
grounded WA legislation research pipeline.

Families:
  1. grounded              — the corpus holds the provision
  2. out_of_corpus         — a real Australian Act that is not recorded
  3. wrong_jurisdiction    — NSW/Victorian problems against the WA corpus
  4. ambiguous_facts       — dates, parties or legal category under-specified
  5. prompt_injection      — instructions hidden in user text and excerpts
  6. tampered_evidence     — mutated digest, foreign host, stale version
  7. scope_refusal         — contract review and document upload by name
  8. near_miss             — section numbers that exist only in another Act
"""
