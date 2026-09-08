"""Fixed provider benchmark over the existing corpus.

Measures each configured provider on the same questions and the same injected
faults, so the default provider is chosen from observed behaviour rather than
from reputation or assumption.

Every answer is put through the real pipeline: retrieval, digest-chained
provision text, citation validation, and quote validation. A "success" here
means a fully validated, fully cited answer, not merely an HTTP 200.

Entailment is measured separately and always through a *different* provider,
so it never grades its own output.

Run:

    uv run --locked python scripts/benchmark_providers.py --repeats 1

Credentials are read from the environment only. Nothing here prints, logs, or
stores a key.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from legal_ai.answering.errors import AnswerModelUnavailable
from legal_ai.answering.models import GroundedAnswer, GroundedAnswerRequest
from legal_ai.answering.providers.chain import ChainedAnswerModel, NamedAnswerModel
from legal_ai.answering.providers.openrouter import ChatCompletionsAnswerModel
from legal_ai.answering.providers.registry import PROVIDERS, build_config
from legal_ai.answering.provisions import FileDerivedProvisionStore
from legal_ai.answering.service import AnswerQuestion, GroundedAnswerService
from legal_ai.answering.verification import (
    ChatCompletionsEntailmentVerifier,
    VerifierUnavailable,
)
from legal_ai.research.corpus import RecordedWaCorpus
from legal_ai.research.models import ResearchQuery
from legal_ai.research.service import ResearchValidated, WaResearchService

CORPUS_ROOT = Path("tests/fixtures/wa_legislation")
ACT = "Road Traffic Act 1974"

S55 = [
    "What must a driver do after damaging property?",
    "What penalty applies for failing to stop after damaging property?",
    "What information must a driver give after damaging property?",
    "Is there a defence if the driver did not know about the incident?",
    "Can a court disqualify a driver for this offence?",
]
S56 = [
    "What must a driver do when an incident causes bodily harm?",
    "Who must a driver report an incident to?",
    "What penalty applies if the incident caused grievous bodily harm?",
    "What defences are available for failing to report an incident?",
    "What must a driver do after an incident causing property damage?",
]
#: Answerable-looking, but nothing in these provisions addresses them. The
#: correct behaviour is an empty draft, which the pipeline turns into a refusal.
UNSUPPORTED = [
    "What is the blood alcohol limit for a learner driver?",
    "How do I appeal a parking fine?",
    "What are the rules for towing a caravan?",
    "Do I need third party property insurance?",
    "What is the speed limit in a school zone?",
]


class _StubTransport:
    """Injected provider faults, so failure handling is measured not assumed."""

    def __init__(self, kind: str) -> None:
        self.kind = kind

    def build(self) -> Any:
        import httpx

        kind = self.kind

        def handler(request: httpx.Request) -> httpx.Response:
            if kind == "malformed":
                return httpx.Response(
                    200, json={"choices": [{"message": {"content": "{not json at all"}}]}
                )
            if kind == "truncated":
                body = '{"propositions": [{"statement": "cut off here'
                return httpx.Response(200, json={"choices": [{"message": {"content": body}}]})
            if kind == "rate_limited":
                return httpx.Response(429, json={"error": {"message": "rate limited"}})
            if kind == "unavailable":
                return httpx.Response(503, json={"error": {"message": "unavailable"}})
            raise AssertionError(f"unknown fault {kind}")

        if kind == "timeout":

            class _Trickle(httpx.SyncByteStream):
                def __iter__(self) -> Any:
                    while True:
                        time.sleep(0.01)
                        yield b'{"padding":"' + b"x" * 256

            def slow(request: httpx.Request) -> httpx.Response:
                return httpx.Response(200, stream=_Trickle())

            return httpx.MockTransport(slow)
        return httpx.MockTransport(handler)


@dataclass
class Tally:
    """Observed behaviour for one provider."""

    provider: str
    model: str
    answered: int = 0
    refused: int = 0
    answerable_total: int = 0
    answerable_ok: int = 0
    unsupported_total: int = 0
    unsupported_refused: int = 0
    quote_ok: int = 0
    quote_total: int = 0
    malformed: int = 0
    latencies: list[float] = field(default_factory=list)
    refusal_codes: dict[str, int] = field(default_factory=dict)
    fault_handled: dict[str, str] = field(default_factory=dict)
    entail_ok: int = 0
    entail_total: int = 0

    def record_refusal(self, code: str) -> None:
        self.refused += 1
        self.refusal_codes[code] = self.refusal_codes.get(code, 0) + 1
        if code == "MODEL_OUTPUT_MALFORMED":
            self.malformed += 1

    @property
    def attempts(self) -> int:
        return self.answered + self.refused

    def summary(self) -> dict[str, Any]:
        ordered = sorted(self.latencies)
        p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))] if ordered else 0.0
        return {
            "provider": self.provider,
            "model": self.model,
            "attempts": self.attempts,
            # Separated deliberately: a refusal on an unsupported question is a
            # correct outcome, and averaging it with failures hides both.
            "answerable_success_rate": (
                round(self.answerable_ok / self.answerable_total, 3)
                if self.answerable_total
                else None
            ),
            "correct_refusal_rate": (
                round(self.unsupported_refused / self.unsupported_total, 3)
                if self.unsupported_total
                else None
            ),
            "overall_answer_rate": round(self.answered / self.attempts, 3)
            if self.attempts
            else 0.0,
            "overall_refusal_rate": round(self.refused / self.attempts, 3)
            if self.attempts
            else 0.0,
            "quote_validation": (
                round(self.quote_ok / self.quote_total, 3) if self.quote_total else None
            ),
            "entailment_success": (
                round(self.entail_ok / self.entail_total, 3) if self.entail_total else None
            ),
            "latency_median_s": round(statistics.median(ordered), 1) if ordered else None,
            "latency_p95_s": round(p95, 1) if ordered else None,
            "malformed_json_rate": (
                round(self.malformed / self.attempts, 3) if self.attempts else 0.0
            ),
            "refusal_codes": self.refusal_codes,
            "fault_handling": self.fault_handled,
        }


def _service(config: Any, verifier: Any) -> tuple[GroundedAnswerService, Any]:
    corpus = RecordedWaCorpus(CORPUS_ROOT)
    store = FileDerivedProvisionStore(CORPUS_ROOT)

    class _Sink:
        def record(self, event: Any) -> None:
            return None

    model = ChainedAnswerModel([NamedAnswerModel(config.name, ChatCompletionsAnswerModel(config))])
    return (
        GroundedAnswerService(
            research=WaResearchService(corpus=corpus, audit_sink=_Sink()),
            model=model,
            provisions=store,
            verifier=verifier,
        ),
        store,
    )


def _query(provision: str) -> ResearchQuery:
    return ResearchQuery(
        jurisdiction="WA",
        act_title=ACT,
        provision_identifier=provision,
        pinpoint=f"section {provision.split()[-1]}",
    )


def _bench_provider(provider: str, model_name: str, verify_with: str | None) -> Tally | None:
    config = build_config(provider, model_name)
    if config is None:
        print(f"  {provider}: not configured, skipping")
        return None

    verifier = None
    if verify_with is not None:
        other = build_config(verify_with, "")
        if other is not None:
            verifier = ChatCompletionsEntailmentVerifier(other)

    tally = Tally(provider=provider, model=config.model)
    service, store = _service(config, None)

    cases = [("s 55", q, True) for q in S55] + [("s 56", q, True) for q in S56]
    cases += [("s 55", q, False) for q in UNSUPPORTED]

    for provision, question, answerable in cases:
        if answerable:
            tally.answerable_total += 1
        else:
            tally.unsupported_total += 1
        started = time.monotonic()
        result = service.answer(AnswerQuestion(question=question, query=_query(provision)))
        elapsed = time.monotonic() - started
        tally.latencies.append(elapsed)

        if isinstance(result, GroundedAnswer):
            tally.answered += 1
            if answerable:
                tally.answerable_ok += 1
            for proposition in result.propositions:
                if proposition.citation.quote is not None:
                    tally.quote_total += 1
                    tally.quote_ok += 1  # a shown quote already passed validation
            if verifier is not None and result.propositions:
                proposition = result.propositions[0]
                packet_text = _provision_text(store, provision)
                tally.entail_total += 1
                try:
                    if verifier.verify(statement=proposition.statement, provision_text=packet_text):
                        tally.entail_ok += 1
                except VerifierUnavailable:
                    pass
        else:
            tally.record_refusal(str(result.code))
            if not answerable and str(result.code) == "NO_PROPOSITIONS":
                # Refusing because the provision is silent is the right answer.
                tally.unsupported_refused += 1

    for fault in ("malformed", "truncated", "timeout", "rate_limited", "unavailable"):
        tally.fault_handled[fault] = _probe_fault(config, fault)

    return tally


def _provision_text(store: FileDerivedProvisionStore, provision: str) -> str:
    corpus = RecordedWaCorpus(CORPUS_ROOT)

    class _Sink:
        def record(self, event: Any) -> None:
            return None

    outcome = WaResearchService(corpus=corpus, audit_sink=_Sink()).research(_query(provision))
    if not isinstance(outcome, ResearchValidated):
        return ""
    derived = store.resolve(outcome.packet)
    return derived.text if derived else ""


def _probe_fault(config: Any, fault: str) -> str:
    """Return the typed outcome for an injected provider fault."""

    adapter = ChatCompletionsAnswerModel(config, transport=_StubTransport(fault).build())
    request = GroundedAnswerRequest(
        question="probe",
        source_id="probe",
        act_title=ACT,
        provision_identifier="s 55",
        pinpoint="section 55",
        provision_heading=None,
        source_version="1",
        compilation_date=None,
        official_source_url="https://www.legislation.wa.gov.au/x",
        sha256="0" * 64,
        source_content=b"x",
        provision_text="the driver must stop",
        provision_sha256="0" * 64,
    )
    try:
        draft = adapter.answer_within(request, deadline_seconds=2.0)
    except AnswerModelUnavailable:
        # What the pipeline turns into the typed MODEL_UNAVAILABLE refusal.
        return "MODEL_UNAVAILABLE"
    except Exception as exc:  # pragma: no cover - a fault that escaped handling
        return f"UNHANDLED:{type(exc).__name__}"
    if not draft.propositions:
        return "NO_PROPOSITIONS"
    return "ANSWERED"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark answer providers.")
    parser.add_argument("--providers", default="", help="comma-separated provider:model pairs")
    args = parser.parse_args(argv)

    targets: list[tuple[str, str]] = []
    if args.providers:
        for item in args.providers.split(","):
            provider, _, model = item.partition(":")
            targets.append((provider.strip(), model.strip()))
    else:
        targets = [(name, "") for name in PROVIDERS]

    results: list[dict[str, Any]] = []
    for provider, model_name in targets:
        other = next((n for n in PROVIDERS if n != provider), None)
        print(f"benchmarking {provider} {model_name or '(default)'} ...", flush=True)
        tally = _bench_provider(provider, model_name, other)
        if tally is not None:
            results.append(tally.summary())

    print()
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
