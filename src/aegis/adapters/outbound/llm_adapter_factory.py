from typing import Dict, Any
from loguru import logger

from .google_genai_adapter import GoogleGenAIAdapter
from .openai_adapter import OpenAIAdapter
from .base import LLMAdapter

def get_llm_adapter(config: Dict[str, Any]) -> LLMAdapter:
    """Factory function to get a singleton instance of the configured LLM adapter."""
    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "google_genai_studio")

    # Simple singleton implementation to avoid re-initializing on every agent step
    if not hasattr(get_llm_adapter, "instance") or get_llm_adapter.provider != provider:
        logger.info(f"Creating new LLM adapter instance for provider: {provider}")
        if provider == "google_genai_studio":
            get_llm_adapter.instance = GoogleGenAIAdapter(config)
        elif provider == "openai":
            get_llm_adapter.instance = OpenAIAdapter(config)
        else:
            raise ValueError(f"Unknown or unsupported LLM provider in config: {provider}")
        get_llm_adapter.provider = provider
    
    return get_llm_adapter.instance