# Provision Routing Scope Card — Model-driven provision selection with deterministic validation

**Branch:** `feat/provision-routing`
**Governing decisions:** ADR 0019 · ADR 0020 (accepted)
**Authority level:** L0 — deterministic validation gate; model selection is advisory only
**Status:** implemented, gates passing; awaiting external review

## Goal

Add a routing layer that lets a user describe a legal problem in natural language;
the router narrows the open catalogue to the most-likely relevant provision(s)
before the existing grounded-answer pipeline is called. All routing decisions are
validated deterministically against the catalogue — the model cannot invent Acts
or sections.

## Delivered

| Path | Purpose |
|---|---|
| `src/legal_ai/answering/routing.py` | `ProvisionRoutingService`, `validate_route`, typed outcomes (`RoutedProvision`, `RouteCandidates`, `RouteRefused`) |
| `src/legal_ai/answering/providers/router.py` | `ChatCompletionsProvisionRouter` — chat-completions call that returns an untrusted `RouterDraft`; bounded response, strict JSON parse |
| `src/legal_ai/api/routes/route.py` | `POST /api/route` — HTTP contract; 503 when no router wired, 200 for all typed refusals |
| `src/legal_ai/api/main.py` | Extended `create_app` with `router` param; `_resolve_router`; wires `app.state.routing_service` |
| `src/legal_ai/api/schemas.py` | `RouteRequestBody`, `RoutedAnswerBody`, `RouteCandidatesBody`, `RouteRefusalBody`, render helpers |
| `src/legal_ai/api/routes/__init__.py` | Exports `route` submodule so mypy resolves the import |
| `static/index.html` | Routing panel: `route-form`, `problem` textarea, `route-result` live region |
| `static/app.js` | `renderRouteResult`, `adoptChoice`, `routeForm` submit handler, `ROUTE_REFUSALS` copy |
| `tests/answering/test_routing.py` | 13 tests — single route, ambiguous candidates, wrong-act/empty rejection, out-of-scope pre-filter, router outage, `validate_route` unit |
| `tests/api/test_route_api.py` | 5 HTTP contract tests — routed answer, candidates, no-match, out-of-scope, 503 |

## Out of scope — deliberately not done

- Any change to the research, casework, evidence-vault, or playbook surfaces
- Vector retrieval or semantic search
- Multi-turn routing dialogue
- Corpus expansion beyond existing fixtures
- Authentication or deployment changes
- Any modification to Phase 0–4 modules

## Acceptance criteria

1. A single-match route returns a grounded answer from the existing pipeline. — **met**
2. Multiple plausible provisions return `CANDIDATES` for user selection. — **met**
3. Invented Acts or sections are dropped by deterministic validation, never coerced. — **met**
4. Out-of-scope questions (contract/drafting) are refused before the model is called. — **met**
5. Router outage returns `ROUTER_UNAVAILABLE` refusal; service stays up. — **met**
6. Empty catalogue returns `CATALOGUE_EMPTY` refusal (503). — **met**
7. `POST /api/route` returns 503 when no router is wired. — **met**
8. All repository gates pass. — **met**

## Validation

```
uv run --locked ruff check .          # All checks passed
uv run --locked ruff format --check . # 207 files already formatted
uv run --locked mypy .                # no issues in 207 source files
uv run --locked pytest -q             # all tests passed (exit 0)
```

## Changed paths (for review gate `--allow`)

```
src/legal_ai/answering/routing.py
src/legal_ai/answering/providers/router.py
src/legal_ai/api/routes/route.py
src/legal_ai/api/routes/__init__.py
src/legal_ai/api/main.py
src/legal_ai/api/schemas.py
static/index.html
static/app.js
tests/answering/test_routing.py
tests/api/test_route_api.py
```

## Rollback

```
git checkout main
git branch -D feat/provision-routing
```

No migration, no schema change, no persisted state, no modification to any pre-existing module.
