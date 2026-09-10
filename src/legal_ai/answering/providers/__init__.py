"""Live answer-model adapters. The mock adapter remains the default."""

from .openrouter import OpenRouterAnswerModel, OpenRouterConfig, load_openrouter_config

__all__ = ["OpenRouterAnswerModel", "OpenRouterConfig", "load_openrouter_config"]
