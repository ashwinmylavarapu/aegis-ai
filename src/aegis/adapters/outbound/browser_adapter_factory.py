from typing import Dict, Any
from loguru import logger

from .browser_adapter import BrowserAdapter
from .noop_browser_adapter import NoOpBrowserAdapter
from .playwright_adapter import PlaywrightAdapter


_browser_adapter_instance = None

def get_browser_adapter(config: Dict[str, Any]) -> BrowserAdapter:
    """
    Factory function to get a singleton instance of the configured browser adapter.
    """
    global _browser_adapter_instance

    if _browser_adapter_instance:
        return _browser_adapter_instance

    browser_config = config.get("browser", {})
    adapter_type = browser_config.get("adapter", "noop")
    logger.info(f"Initializing browser adapter of type: '{adapter_type}'")

    if adapter_type == "playwright":
        _browser_adapter_instance = PlaywrightAdapter(config)
    elif adapter_type == "noop":
        _browser_adapter_instance = NoOpBrowserAdapter()
    else:
        raise ValueError(f"Unknown browser adapter type in config: {adapter_type}")
    
    return _browser_adapter_instance