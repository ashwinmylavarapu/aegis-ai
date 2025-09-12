from abc import ABC, abstractmethod
from typing import List, Dict, Any

class LLMAdapter(ABC):
    @abstractmethod
    async def generate_plan(self, goal: str, history: List[Dict[str, Any]] = []) -> List[Dict[str, Any]]:
        """Generates a plan from a natural language goal and conversation history."""
        pass