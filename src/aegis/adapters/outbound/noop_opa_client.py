from typing import Dict, Any, List
from .opa_client import OPAClient

class NoOpOPAClient(OPAClient):
    """A no-op implementation of the OPAClient that always returns true."""

    def __init__(self):
        pass

    async def check_policy(self, input_data: Dict[str, Any]) -> bool:
        """Always returns True, effectively disabling the policy check."""
        return True

    # --- THIS IS THE FIX ---
    # We add the missing 'check_plan' method required by the OPAClient base class.
    # For a no-op client, we simply return the plan unchanged, effectively approving it.
    async def check_plan(self, plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Always returns the plan as-is, effectively disabling plan-level checks."""
        return plan