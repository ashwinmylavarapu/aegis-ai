from typing import List, Dict, Any
from .opa_client import OPAClient

class NoOpOPAClient(OPAClient):
    def check_plan(self, plan: List[Dict[str, Any]]) -> bool:
        """
        A No-Op OPA client that mimics the Rego policy in Python.
        It checks that all 'navigate' actions are to allowed domains.
        """
        print("--- Using NoOpOPAClient ---")
        allowed_domains = ["jobs.our-company.com", "internal.our-company.com"]

        for step in plan:
            if step.get("action") == "navigate":
                url = step.get("url", "")
                if not any(url.endswith(domain) for domain in allowed_domains):
                    print(f"    Policy VIOLATION: Navigation to '{url}' is not allowed.")
                    return False
        
        print("    Policy check PASSED.")
        return True
