"""Named chat-completions providers, resolved from the environment.

Every provider here speaks the same OpenAI-style `/chat/completions` shape, so
one adapter serves all of them and only the endpoint, credential, and model
differ. Adding a provider is a row in `PROVIDERS`, not a new client.

Credentials are read from the environment and never logged, printed, defaulted,
or embedded. A provider whose key is absent is simply not available, which is
why an unconfigured fallback is skipped rather than failing the request.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from .openrouter import ProviderConfig, validated_base_url

_LOGGER = logging.getLogger("legal_ai.answering.providers")

MOCK = "mock"


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    """How to reach one named provider."""

    env_api_key: str
    base_url: str
    default_model: str


#: The providers this build knows how to talk to.
PROVIDERS: dict[str, ProviderSpec] = {
    "openrouter": ProviderSpec(
        env_api_key="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        default_model="google/gemini-3.7-flash",
    ),
    "deepseek": ProviderSpec(
        env_api_key="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com",
        default_model="deepseek-v4-flash",
    ),
}

ENV_ANSWER_PROVIDER = "LEGAL_AI_ANSWER_PROVIDER"
ENV_ANSWER_MODEL = "LEGAL_AI_ANSWER_MODEL"
ENV_FALLBACK_PROVIDER = "LEGAL_AI_FALLBACK_PROVIDER"
ENV_FALLBACK_MODEL = "LEGAL_AI_FALLBACK_MODEL"
ENV_FINAL_PROVIDER = "LEGAL_AI_FINAL_FALLBACK_PROVIDER"
ENV_FINAL_MODEL = "LEGAL_AI_FINAL_FALLBACK_MODEL"
ENV_VERIFY_PROVIDER = "LEGAL_AI_VERIFY_PROVIDER"
ENV_VERIFY_MODEL = "LEGAL_AI_VERIFY_MODEL"

#: `LEGAL_AI_ANSWER_MODEL` used to name the adapter kind rather than the model.
#: These values keep an existing launch command working instead of silently
#: reinterpreting them as model identifiers.
_LEGACY_ADAPTER_NAMES = frozenset({MOCK, "openrouter"})


def _clean(name: str) -> str:
    return os.environ.get(name, "").strip()


def build_config(provider: str, model: str = "") -> ProviderConfig | None:
    """Return a usable config for a named provider, or None if unavailable.

    None means "not configured", which a caller treats as a provider to skip.
    It never means "fall back to something else silently".
    """

    spec = PROVIDERS.get(provider)
    if spec is None:
        return None
    api_key = _clean(spec.env_api_key)
    if not api_key:
        return None
    base_url = validated_base_url(_clean(f"LEGAL_AI_{provider.upper()}_BASE_URL") or spec.base_url)
    if base_url is None:
        return None
    return ProviderConfig(
        api_key=api_key,
        model=model.strip() or spec.default_model,
        base_url=base_url,
        name=provider,
    )


def answer_provider_name() -> str:
    """Resolve the requested primary answer provider, honouring the old name."""

    requested = _clean(ENV_ANSWER_PROVIDER).lower()
    if requested:
        return requested
    legacy = _clean(ENV_ANSWER_MODEL).lower()
    if legacy in _LEGACY_ADAPTER_NAMES:
        # Read as the adapter kind it used to mean, so an existing command line
        # keeps working. Announced once, because the meaning has changed.
        _LOGGER.warning(
            "%s=%s is being read as a provider name for backward compatibility; set %s instead",
            ENV_ANSWER_MODEL,
            legacy,
            ENV_ANSWER_PROVIDER,
        )
        return legacy
    return MOCK


def answer_chain_specs() -> tuple[tuple[str, str], ...]:
    """Return the ordered (provider, model) chain for answering.

    Primary, then fallback, then an optional final fallback. Duplicates and
    unnamed slots are dropped so the chain is exactly what was asked for.
    """

    legacy = _clean(ENV_ANSWER_MODEL).lower() in _LEGACY_ADAPTER_NAMES
    requested: list[tuple[str, str]] = [
        (answer_provider_name(), "" if legacy else _clean(ENV_ANSWER_MODEL)),
        (_clean(ENV_FALLBACK_PROVIDER).lower(), _clean(ENV_FALLBACK_MODEL)),
        (_clean(ENV_FINAL_PROVIDER).lower(), _clean(ENV_FINAL_MODEL)),
    ]
    chain: list[tuple[str, str]] = []
    for provider, model in requested:
        if provider and provider != MOCK and (provider, model) not in chain:
            chain.append((provider, model))
    return tuple(chain)


def verify_chain_specs() -> tuple[tuple[str, str], ...]:
    """Return the ordered (provider, model) chain for entailment verification.

    Defaults to every configured provider that is not the primary answer
    provider, so level 3 is independent by construction rather than by luck.
    """

    requested = _clean(ENV_VERIFY_PROVIDER).lower()
    if requested:
        return ((requested, _clean(ENV_VERIFY_MODEL)),)

    primary = answer_provider_name()
    others = [(name, "") for name in PROVIDERS if name != primary]
    # The primary is still listed last: a same-provider check is weaker than an
    # independent one, but it is far better than no check, and the pipeline
    # refuses outright if none of these can be built.
    return tuple(others + [(primary, "")])
