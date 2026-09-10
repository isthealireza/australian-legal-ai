"""Offline guard for the entailment verifier's *intent*.

`fix/entailment-false-negatives` changed two things in `verification.py`:

- the prompt now treats a faithful but partial summary (one that omits an
  exception or proviso the text also contains) as SUPPORTED; and
- `MAX_VERIFIER_TOKENS` was raised so a reasoning verify model's trace plus the
  one-word verdict fit, instead of truncating into a spurious refusal.

Neither can be exercised against a live model in CI, so this locks the intent
two ways that a later prompt or budget edit cannot silently undo:

1. Replay tests. Each representative (statement, provision) pair is paired with
   the verdict the live `deepseek-v4-flash` verifier actually returned under the
   current prompt on 2026-09-09 (see docs/execution/LIVE_ADVERSARIAL_RUN_2.md
   and the fix scope card). A recorded transport replays that verdict and the
   test asserts the code maps it to the right decision. The recorded verdicts
   are the ground truth; if the prompt is reworded these must be re-recorded.
2. Prompt/budget assertions. The prompt must still say a partial-but-accurate
   summary is supported and must still refuse invented figures; the token
   budget must stay large enough to clear a reasoning trace. Reverting either
   fails here.
"""

from __future__ import annotations

import json

import httpx
import pytest

from legal_ai.answering.providers.openrouter import OpenRouterConfig
from legal_ai.answering.verification import (
    MAX_VERIFIER_TOKENS,
    VERIFIER_SYSTEM_PROMPT,
    OpenRouterEntailmentVerifier,
)
from tests.research.conftest import RECORDED_FIXTURE_ROOT

_CONFIG = OpenRouterConfig(api_key="k", model="m", base_url="https://example.invalid")


def _provision(act_dir: str, section_file: str) -> str:
    return (RECORDED_FIXTURE_ROOT / act_dir / "provisions" / section_file).read_text(
        encoding="utf-8"
    )


#: (label, provision text, statement, verdict the live verifier recorded, expected bool).
#: The statement text is embedded verbatim in the outgoing prompt, so the replay
#: transport keys off it; the recorded verdict is what deepseek-v4-flash returned
#: under the current prompt (3/3 or 2/2 runs, see the fix validation).
_CASES = [
    (
        "omits_exception_is_supported",
        _provision("sale_of_goods_act_1895", "s_14.txt"),
        # A faithful restatement of s 14(3) that omits the "if the buyer has
        # examined the goods" proviso. Partial but accurate: must be SUPPORTED.
        "Where goods are bought by description from a seller who deals in goods of that "
        "description, there is an implied condition that the goods shall be of merchantable "
        "quality.",
        "SUPPORTED",
        True,
    ),
    (
        "wrong_figure_still_refuses",
        _provision("road_traffic_act_1974", "s_55.txt"),
        # s 55 is a fine of 30 PU, not 300. A wrong number must never pass.
        "The penalty for failing to stop under section 55 is a fine of 300 PU.",
        "NOT_SUPPORTED",
        False,
    ),
    (
        "contradiction_still_refuses",
        _provision("sale_of_goods_act_1895", "s_14.txt"),
        # s 14 preserves implied conditions in (2)-(5); claiming it abolishes
        # them all contradicts the text.
        "Section 14 abolishes all implied conditions and warranties as to the quality or "
        "fitness of goods.",
        "NOT_SUPPORTED",
        False,
    ),
    (
        "invented_condition_still_refuses",
        _provision("owner_drivers_contracts_and_disputes_act_2007", "s_7.txt"),
        # s 7 makes waivers ineffective; a "valid if signed and witnessed" rule
        # is invented and not in the text.
        "Under section 7 a waiver of rights is valid if it is signed by both parties "
        "and witnessed.",
        "NOT_SUPPORTED",
        False,
    ),
]


def _replay_verifier(statement_to_verdict: dict[str, str]) -> OpenRouterEntailmentVerifier:
    """A verifier whose transport replays a recorded verdict for each statement.

    No network and no model: the handler reads the statement out of the outgoing
    prompt and returns exactly the verdict that was recorded for it.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        user = json.loads(request.content)["messages"][1]["content"]
        # The adapter always ends the user turn with "Statement: <statement>".
        statement = user.split("Statement:", 1)[1].strip()
        verdict = statement_to_verdict[statement]
        return httpx.Response(200, json={"choices": [{"message": {"content": verdict}}]})

    return OpenRouterEntailmentVerifier(_CONFIG, transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    ("label", "provision", "statement", "recorded_verdict", "expected"),
    _CASES,
    ids=[case[0] for case in _CASES],
)
def test_recorded_verdicts_map_to_the_intended_decision(
    label: str, provision: str, statement: str, recorded_verdict: str, expected: bool
) -> None:
    verifier = _replay_verifier({statement: recorded_verdict})
    assert verifier.verify(statement=statement, provision_text=provision) is expected


def test_prompt_still_permits_partial_but_accurate_summaries() -> None:
    """The core of the fix: omitting an exception is not grounds for refusal."""

    lowered = VERIFIER_SYSTEM_PROMPT.lower()
    assert "partial but accurate" in lowered
    assert "exception" in lowered and "proviso" in lowered
    # The old wording that produced the false negatives must not creep back.
    assert "when in doubt, answer not_supported" not in lowered
    assert "generalises beyond it" not in lowered


def test_prompt_still_refuses_invented_figures_and_contradictions() -> None:
    """Loosening the gate would drop these commitments; they must remain."""

    lowered = VERIFIER_SYSTEM_PROMPT.lower()
    assert "not_supported" in lowered
    assert "contradicts the text" in lowered
    # An invented number/penalty/term/date must still refuse.
    for token in ("number", "penalty", "term", "date"):
        assert token in lowered


def test_verifier_token_budget_clears_a_reasoning_trace() -> None:
    """Guard the reliability half: a small budget truncated the verdict away."""

    assert MAX_VERIFIER_TOKENS >= 4_096
