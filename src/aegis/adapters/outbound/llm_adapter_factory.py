"""
LLM Adapter Factory
"""
from typing import Dict, Any
from loguru import logger

class MockLLMAdapter:
    """A mock LLM adapter that returns a hardcoded plan."""
    def generate_plan(self, prompt: str):
        logger.info("Using MockLLMAdapter to generate a hardcoded plan.")
        return [
            {"skill": "internal_auth.login"},
            {"action": "navigate", "url": "https://jobs.our-company.com/search"},
            {"action": "type_text", "selector": "#search-keyword-input", "text": "Senior Python Developer"},
            {"action": "click", "selector": "button[type='submit']"},
            {"action": "wait_for_element", "selector": ".search-results-list"},
            {
                "action": "extract_data",
                "selector": ".job-result-card",
                "limit": 3,
                "fields": ["title", "team", "url"],
                "output_file": "job_results.csv"
            }
        ]

def get_llm_adapter(config: Dict[str, Any]):
    """Factory function to get the configured LLM adapter."""
    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "mock")

    if provider == "mock":
        return MockLLMAdapter()
    # Add other providers here in the future (e.g., openai, google)
    else:
        logger.warning(f"Unknown LLM provider '{provider}'. Falling back to MockLLMAdapter.")
        return MockLLMAdapter()