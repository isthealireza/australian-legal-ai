"""Deterministic mock answer model (Phase 5).

The mock exists so the whole grounded pipeline can be exercised end to end with
no provider, no credentials, no network, and no cost. It is not a language
model and does not paraphrase: it restates only identity fields taken from the
evidence packet it was handed, so its output validates by construction.

It is wired as the default adapter. Selecting a live provider is Phase 11 work
and is gated behind the evaluation metrics in MVP_ROADMAP section 9.
"""

from __future__ import annotations

from .models import DraftCitation, DraftProposition, GroundedAnswerRequest, ModelDraft


class MockAnswerModel:
    """A provider-free adapter that restates the packet it was given."""

    name = "mock"

    def answer(self, request: GroundedAnswerRequest) -> ModelDraft:
        """Return one proposition describing the retrieved provision."""

        heading = request.provision_heading
        described = f"{request.pinpoint} of the {request.act_title}"
        if heading is not None:
            statement = f"The retrieved provision {described} is headed '{heading}'."
        else:
            statement = f"The retrieved provision is {described}."

        # When verified provision text is available, quote its opening line
        # verbatim. It is a literal substring by construction, so the mock path
        # exercises quote validation rather than bypassing it.
        quote: str | None = None
        if request.provision_text is not None:
            first_line = request.provision_text.strip().splitlines()[0].strip()
            quote = first_line[:4096] or None

        return ModelDraft(
            propositions=(
                DraftProposition(
                    statement=statement,
                    citation=DraftCitation(
                        source_id=request.source_id,
                        provision_identifier=request.provision_identifier,
                        pinpoint=request.pinpoint,
                        sha256=request.sha256,
                        quote=quote,
                    ),
                ),
            )
        )
