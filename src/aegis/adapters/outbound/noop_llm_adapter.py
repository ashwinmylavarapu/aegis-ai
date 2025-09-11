from typing import List, Dict, Any
from .base import LLMAdapter

class NoOpLLMAdapter(LLMAdapter):
    def generate_plan(self, goal: str) -> List[Dict[str, Any]]:
        print("--- Using NoOpLLMAdapter ---")
        # This is a dummy plan, mimicking the example from the architecture document.
        dummy_plan = [
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
        return dummy_plan
