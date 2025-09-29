# src/aegis/adapters/outbound/native_os_adapter_factory.py
import sys
from typing import Dict, Any
from loguru import logger

from .native_os_adapter import NativeOSAdapter
from .apple_script_os_adapter import AppleScriptOSAdapter

_adapter_instance = None

def get_native_os_adapter(config: Dict[str, Any]) -> NativeOSAdapter:
    """Factory function to get a singleton instance of the correct NativeOSAdapter."""
    global _adapter_instance
    if _adapter_instance:
        return _adapter_instance

    platform = sys.platform
    logger.info(f"Initializing NativeOSAdapter for platform: '{platform}'")

    if platform == "darwin":  # macOS
        _adapter_instance = AppleScriptOSAdapter(config)
    # Future expansion:
    # elif platform == "win32":
    #     from .windows_os_adapter import WindowsOSAdapter
    #     _adapter_instance = WindowsOSAdapter(config)
    else:
        raise NotImplementedError(f"NativeOSAdapter not implemented for platform: {platform}")

    return _adapter_instance