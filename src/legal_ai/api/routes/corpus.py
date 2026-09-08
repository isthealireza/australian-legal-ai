"""What the indexed corpus actually contains.

The interface needs this so a user can choose a real provision instead of
guessing an identifier. Offering only what is indexed is also a safety
property: it keeps a user from asking about an authority the system does not
hold, which could only ever produce a refusal.

The listing describes provisions. It never returns their text.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..schemas import CorpusBody, render_catalogue

router = APIRouter(tags=["corpus"])


@router.get("/api/corpus")
def corpus(request: Request) -> CorpusBody:
    """List the Acts and provisions available to research."""

    return render_catalogue(getattr(request.app.state, "catalogue", ()))
