from .opa_client import OPAClient
from .noop_opa_client import NoOpOPAClient

def get_opa_client(client_type: str = "noop") -> OPAClient:
    """
    Factory function to get an instance of an OPA client.
    """
    if client_type == "noop":
        return NoOpOPAClient()
    else:
        raise ValueError(f"Unknown OPA client type: {client_type}")
