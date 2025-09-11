"""
LLM Adapter Factory
"""
from typing import Dict, Any
from loguru import logger

from .openai_adapter import OpenAIAdapter
from .google_genai_adapter import GoogleGenAIAdapter

class MockLLMAdapter:
    """A mock LLM adapter that returns a hardcoded plan."""
    def generate_plan(self, prompt: str, history=None): # Added history for interface consistency
        logger.info("Using MockLLMAdapter to generate a hardcoded plan for LinkedIn.")
        # This mock plan is now obsolete with working LLMs but kept for testing.
        return [
            {"action": "navigate", "url": "https://www.linkedin.com/jobs"},
        ]

def get_llm_adapter(config: Dict[str, Any]):
    """Factory function to get the configured LLM adapter."""
    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "mock")

    # Simple singleton implementation
    if not hasattr(get_llm_adapter, "instance") or get_llm_adapter.provider != provider:
        logger.info(f"Creating new LLM adapter instance for provider: {provider}")
        if provider == "mock":
            get_llm_adapter.instance = MockLLMAdapter()
        elif provider == "openai":
            get_llm_adapter.instance = OpenAIAdapter(config)
        elif provider == "google_genai_studio":
            get_llm_adapter.instance = GoogleGenAIAdapter(config)
        else:
            logger.warning(f"Unknown LLM provider '{provider}'. Falling back to MockLLMAdapter.")
            get_llm_adapter.instance = MockLLMAdapter()
        get_llm_adapter.provider = provider
    
    return get_llm_adapter.instance