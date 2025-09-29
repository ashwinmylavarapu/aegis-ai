# src/aegis/adapters/outbound/native_os_adapter.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class NativeOSAdapter(ABC):
    """Abstract base class for native operating system interactions."""

    @abstractmethod
    async def launch_app(self, app_name: str, file_path: Optional[str] = None) -> str:
        """Launches a native application, optionally opening a file."""
        pass
    
    @abstractmethod
    async def focus_app(self, app_name: str) -> str:
        """Brings an already-running application to the foreground."""
        pass

    @abstractmethod
    async def quit_app(self, app_name: str) -> str:
        """Quits a native application."""
        pass
    
    @abstractmethod
    async def write_file(self, file_path: str, content: str) -> str:
        """Writes content to a local file."""
        pass

    @abstractmethod
    async def delete_file(self, file_path: str) -> str:
        """Deletes a local file."""
        pass

    @abstractmethod
    async def press_key_native(self, key: str, modifier: str = "", app_name: Optional[str] = None) -> str:
        """Presses a key or key combination at the OS level, targeting a specific app."""
        pass

    @abstractmethod
    async def type_text_native(self, text: str, app_name: Optional[str] = None) -> str:
        """Types a string of text at the OS level into a specific app."""
        pass

    @abstractmethod
    async def read_screen_content(self) -> str:
        """Captures the screen and uses OCR to extract all visible text."""
        pass