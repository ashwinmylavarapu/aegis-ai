"""
LLM Adapter Factory
"""

class MockLLMAdapter:
    """A mock LLM adapter that returns a hardcoded plan."""
    def generate_plan(self, prompt: str):
        print("    (Using MockLLMAdapter to generate a hardcoded plan)")
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

def get_llm_adapter():
    """Factory function to get the configured LLM adapter."""
    # In a real scenario, this would read a config file.
    # For now, it returns the mock adapter.
    return MockLLMAdapter()