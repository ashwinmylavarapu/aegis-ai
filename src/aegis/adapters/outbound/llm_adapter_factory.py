"""
Factory to get the configured LLM adapter.
"""
from typing import List, Dict, Any

class LLMAdapter:
    """Placeholder for the real LLM adapter."""
    def generate_plan(self, goal: str) -> List[Dict[str, Any]]:
        print(f"--- Mock LLM: Generating plan for goal: {goal[:50]}...")
        # This is a mock plan that aligns with the example in the arch doc
        return [
            { "skill": "internal_auth.login" },
            { "action": "navigate", "url": "https://jobs.our-company.com/search" },
            { "action": "type_text", "selector": "#search-keyword-input", "text": "Senior Python Developer" },
            { "action": "click", "selector": "button[type='submit']" },
            { "action": "wait_for_element", "selector": ".search-results-list" },
            { 
              "action": "extract_data", 
              "selector": ".job-result-card", 
              "limit": 3, 
              "fields": ["title", "team", "url"],
              "output_file": "job_results.csv"
            }
        ]

def get_llm_adapter():
    """Returns a singleton instance of the LLM adapter."""
    # In a real app, this would read config and instantiate the correct adapter.
    return LLMAdapter()