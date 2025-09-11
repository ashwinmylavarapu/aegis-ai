from abc import ABC, abstractmethod
from typing import List, Dict, Any

class OPAClient(ABC):
    @abstractmethod
    def check_plan(self, plan: List[Dict[str, Any]]) -> bool:
        """Checks if a plan is allowed by the policy. Returns True if allowed, False otherwise."""
        pass
