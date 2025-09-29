# src/aegis/adapters/outbound/native_os_adapter.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple

class NativeOSAdapter(ABC):
    """Abstract base class for native operating system interactions."""

    @abstractmethod
    async def launch_app(self, app_name: str, file_path: Optional[str] = None) -> str:
        """Launches a native application, optionally opening a file."""
        pass

    @abstractmethod
    async def quit_app(self, app_name: str) -> str:
        """Quits a native application."""
        pass

    @abstractmethod
    async def list_windows(self, app_name: str) -> List[str]:
        """Lists the titles of all open windows for a given application."""
        pass
    
    @abstractmethod
    async def focus_window(self, app_name: str, window_title: str) -> str:
        """Brings a specific window of an application to the foreground."""
        pass

    @abstractmethod
    async def get_window_bounds(self, app_name: str, window_title: str) -> Dict[str, int]:
        """Gets the position and size (x, y, width, height) of a specific window."""
        pass

    @abstractmethod
    async def set_window_bounds(self, app_name: str, window_title: str, x: Optional[int] = None, y: Optional[int] = None, width: Optional[int] = None, height: Optional[int] = None) -> str:
        """Moves and/or resizes a specific window."""
        pass

    @abstractmethod
    async def write_file(self, file_path: str, content: str, executable: bool = False) -> str:
        """Writes content to a local file, optionally making it executable."""
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

    @abstractmethod
    async def read_clipboard(self) -> str:
        """Reads the current text content from the system clipboard."""
        pass

    @abstractmethod
    async def write_clipboard(self, text: str) -> str:
        """Writes text content to the system clipboard."""
        pass

    @abstractmethod
    async def run_script(self, script_path: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """Executes a local script and returns its output."""
        pass

    @classmethod
    @abstractmethod
    def get_tools(cls) -> List[dict]:
        """Returns a list of tool definitions for the adapter."""
        pass