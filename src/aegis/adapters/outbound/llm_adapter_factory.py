# src/aegis/adapters/outbound/llm_adapter_factory.py
from typing import Dict, Any, List
from loguru import logger

from .base import LLMAdapter
from .google_genai_adapter import GoogleGenAIAdapter
from .openai_adapter import OpenAIAdapter
from .noop_llm_adapter import NoOpLLMAdapter

_llm_adapter_instance = None


def get_llm_adapter(config: Dict[str, Any], tools: List[Dict[str, Any]] = None) -> LLMAdapter:
    """
    Factory function to get a singleton instance of the configured LLM adapter.
    """
    global _llm_adapter_instance

    if _llm_adapter_instance and not tools:
        return _llm_adapter_instance

    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "noop")
    logger.info(f"Initializing LLM adapter of type: '{provider}'")

    if provider == "google_genai_studio":
        instance = GoogleGenAIAdapter(config, tools=tools)
    elif provider == "openai":
        instance = OpenAIAdapter(config, tools=tools)
    elif provider == "noop":
        instance = NoOpLLMAdapter()
    else:
        raise ValueError(f"Unknown LLM provider type: {provider}")

    if not tools:
        _llm_adapter_instance = instance
        
    return instance