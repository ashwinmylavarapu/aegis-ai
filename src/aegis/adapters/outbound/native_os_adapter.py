# src/aegis/adapters/outbound/native_os_adapter.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class NativeOSAdapter(ABC):
    """Abstract base class for native operating system interactions."""

    @abstractmethod
    async def press_key_native(self, key: str, modifier: str = "") -> str:
        """Presses a key or key combination at the OS level."""
        pass

    @abstractmethod
    async def type_text_native(self, text: str) -> str:
        """Types a string of text at the OS level."""
        pass

    @abstractmethod
    async def read_screen_content(self) -> str:
        """Captures the screen and uses OCR to extract all visible text."""
        pass