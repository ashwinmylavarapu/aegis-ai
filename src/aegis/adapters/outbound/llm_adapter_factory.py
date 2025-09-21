# src/aegis/adapters/outbound/llm_adapter_factory.py
from typing import Dict, Any
from loguru import logger

from .base import LLMAdapter
from .google_genai_adapter import GoogleGenAIAdapter
from .openai_adapter import OpenAIAdapter
from .noop_llm_adapter import NoOpLLMAdapter

_llm_adapter_instance = None


def get_llm_adapter(config: Dict[str, Any]) -> LLMAdapter:
    """Factory function to get a singleton instance of the configured LLM adapter."""
    global _llm_adapter_instance

    if _llm_adapter_instance:
        return _llm_adapter_instance

    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "noop")
    logger.info(f"Initializing LLM adapter of type: '{provider}'")

    if provider == "google_genai_studio":
        _llm_adapter_instance = GoogleGenAIAdapter(config)
    elif provider == "openai":
        _llm_adapter_instance = OpenAIAdapter(config)
    elif provider == "noop":
        _llm_adapter_instance = NoOpLLMAdapter()
    else:
        raise ValueError(f"Unknown LLM provider type: {provider}")

    return _llm_adapter_instance