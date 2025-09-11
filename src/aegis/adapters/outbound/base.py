from abc import ABC, abstractmethod
from typing import List, Dict, Any

class LLMAdapter(ABC):
    @abstractmethod
    def generate_plan(self, goal: str) -> List[Dict[str, Any]]:
        """Generates a plan from a natural language goal."""
        pass
