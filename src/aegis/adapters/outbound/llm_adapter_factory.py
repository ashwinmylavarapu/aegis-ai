# src/aegis/adapters/outbound/llm_adapter_factory.py
from typing import Dict, Any
from loguru import logger

from .base import LLMAdapter
from .google_genai_adapter import GoogleGenAIAdapter
from .openai_adapter import OpenAIAdapter
from .noop_llm_adapter import NoOpLLMAdapter

_llm_adapter_instance = None


def get_llm_adapter(config: Dict[str, Any], **kwargs) -> LLMAdapter:
    """
    Factory function to get a singleton instance of the configured LLM adapter.
    Using a singleton for the tool is not ideal, so we will bypass it for now.
    """
    global _llm_adapter_instance

    # For tools, we might re-initialize, so bypass singleton if kwargs are passed
    if _llm_adapter_instance and not kwargs:
        return _llm_adapter_instance

    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "noop")
    logger.info(f"Initializing LLM adapter of type: '{provider}'")

    if provider == "google_genai_studio":
        instance = GoogleGenAIAdapter(config, **kwargs)
    elif provider == "openai":
        instance = OpenAIAdapter(config, **kwargs) # Assuming OpenAIAdapter might also be adapted
    elif provider == "noop":
        instance = NoOpLLMAdapter()
    else:
        raise ValueError(f"Unknown LLM provider type: {provider}")

    # Don't store the instance as a singleton if it's a special build (e.g., for a tool)
    if not kwargs:
        _llm_adapter_instance = instance
        
    return instance