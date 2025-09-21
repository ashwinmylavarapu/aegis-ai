# src/aegis/adapters/outbound/omni_parser_adapter_factory.py
from typing import Any, Dict
from loguru import logger

from .omni_parser_adapter import OmniParserAdapter

_adapter_instance = None

def get_omni_parser_adapter(config: Dict[str, Any]) -> OmniParserAdapter:
    """Factory function to get a singleton instance of the OmniParserAdapter."""
    global _adapter_instance

    if _adapter_instance:
        return _adapter_instance

    parser_config = config.get("omni_parser_adapter")
    if not parser_config:
        raise ValueError("omni_parser_adapter configuration is missing from config.yaml")

    logger.info("Initializing OmniParserAdapter.")
    _adapter_instance = OmniParserAdapter(parser_config)
    return _adapter_instance