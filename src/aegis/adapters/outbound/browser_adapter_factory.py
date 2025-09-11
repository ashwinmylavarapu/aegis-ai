from .browser_adapter import BrowserAdapter
from .noop_browser_adapter import NoOpBrowserAdapter

def get_browser_adapter(adapter_type: str = "noop") -> BrowserAdapter:
    """
    Factory function to get an instance of a browser adapter.
    """
    if adapter_type == "noop":
        return NoOpBrowserAdapter()
    # In the future, this could return a real BrowserMCPAdapter
    # elif adapter_type == "browsermcp":
    #     return BrowserMCPAdapter()
    else:
        raise ValueError(f"Unknown browser adapter type: {adapter_type}")
