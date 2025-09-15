from typing import Dict, Any
from .opa_client import OPAClient
from .noop_opa_client import NoOpOPAClient

_opa_client_instance = None

def get_opa_client(config: Dict[str, Any]) -> OPAClient:
    global _opa_client_instance
    if _opa_client_instance is None:
        opa_config = config.get("opa", {})
        provider = opa_config.get("provider", "noop")

        if provider == "http":
            _opa_client_instance = OPAClient(config)
        elif provider == "noop":
            # --- THIS IS THE FIX ---
            # The NoOpOPAClient takes no arguments, so we pass none.
            _opa_client_instance = NoOpOPAClient()
        else:
            raise ValueError(f"Unknown OPA provider type: {provider}")
    return _opa_client_instance