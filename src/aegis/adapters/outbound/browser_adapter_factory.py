from typing import Dict, Any
from loguru import logger

from .browser_adapter import BrowserAdapter
from .noop_browser_adapter import NoOpBrowserAdapter
from .browser_mcp_adapter import BrowserMCPAdapter # Changed import

_browser_adapter_instance = None

def get_browser_adapter(config: Dict[str, Any]) -> BrowserAdapter:
    global _browser_adapter_instance

    if _browser_adapter_instance:
        return _browser_adapter_instance

    browser_config = config.get("browser", {})
    adapter_type = browser_config.get("adapter", "noop")
    logger.info(f"Initializing browser adapter of type: '{adapter_type}'")

    if adapter_type == "browsermcp": # Changed condition
        _browser_adapter_instance = BrowserMCPAdapter(config)
    elif adapter_type == "noop":
        _browser_adapter_instance = NoOpBrowserAdapter()
    else:
        raise ValueError(f"Unknown browser adapter type in config: {adapter_type}")
    
    return _browser_adapter_instance