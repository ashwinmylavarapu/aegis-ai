# src/aegis/adapters/outbound/apple_script_os_adapter.py
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime
from loguru import logger
from typing import Dict, Any, Optional
import asyncio

from .native_os_adapter import NativeOSAdapter

log = logger.bind(adapter_name="AppleScriptOSAdapter")

class AppleScriptOSAdapter(NativeOSAdapter):
    """An adapter for native macOS interactions using AppleScript and Python's os module."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config.get("native_os", {})
        self.default_target_app = self.config.get("target_app")
        self.debug_dir = "debug_screenshots"
        os.makedirs(self.debug_dir, exist_ok=True)
        log.info(f"Initialized with default_target_app: '{self.default_target_app}'")

    async def _capture_desktop_evidence(self, context: str, stage: str):
        """Helper to capture a screenshot of the entire desktop."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = os.path.join(self.debug_dir, f"{timestamp}_{context}_{stage}.png")
        try:
            process = await asyncio.create_subprocess_exec("screencapture", "-C", path)
            await process.wait()
            log.debug(f"Saved desktop screenshot for '{context}' to '{path}'")
        except Exception as e:
            log.error(f"Failed to capture desktop screenshot: {e}")

    async def launch_app(self, app_name: str, file_path: Optional[str] = None) -> str:
        """Launches an application, optionally opening a specific file."""
        func_log = log.bind(function_name="launch_app", params={"app_name": app_name, "file_path": file_path})
        await self._capture_desktop_evidence(f"launch_{app_name}", "before")

        script = ""
        if file_path:
            abs_path = os.path.abspath(file_path)
            script = f'tell application "{app_name}" to open POSIX file "{abs_path}"\n'
        
        script += f'tell application "{app_name}" to activate'

        try:
            func_log.info(f"Launching and activating '{app_name}'...")
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
            await self._capture_desktop_evidence(f"launch_{app_name}", "after")
            return f"Successfully launched '{app_name}'" + (f" with file '{file_path}'." if file_path else ".")
        except subprocess.CalledProcessError as e:
            func_log.error("Failed to launch application", stderr=e.stderr)
            await self._capture_desktop_evidence(f"launch_{app_name}", "error")
            return f"Error launching '{app_name}': {e.stderr}"

    async def focus_app(self, app_name: str) -> str:
        """Brings an already-running application to the foreground."""
        func_log = log.bind(function_name="focus_app", params={"app_name": app_name})
        await self._capture_desktop_evidence(f"focus_{app_name}", "before")
        script = f'tell application "{app_name}" to activate'
        try:
            func_log.info(f"Changing focus to '{app_name}'...")
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
            await self._capture_desktop_evidence(f"focus_{app_name}", "after")
            return f"Successfully focused on '{app_name}'."
        except subprocess.CalledProcessError as e:
            func_log.error("Failed to focus application", stderr=e.stderr)
            await self._capture_desktop_evidence(f"focus_{app_name}", "error")
            return f"Error focusing on '{app_name}': {e.stderr}"

    async def quit_app(self, app_name: str) -> str:
        """Quits an application."""
        func_log = log.bind(function_name="quit_app", params={"app_name": app_name})
        script = f'quit app "{app_name}"'
        try:
            func_log.info(f"Quitting '{app_name}'...")
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
            return f"Successfully quit '{app_name}'."
        except subprocess.CalledProcessError as e:
            func_log.error("Failed to quit application", stderr=e.stderr)
            return f"Error quitting '{app_name}': {e.stderr}"

    async def write_file(self, file_path: str, content: str) -> str:
        """Writes content to a local file using Python's Pathlib."""
        func_log = log.bind(function_name="write_file", params={"file_path": file_path})
        try:
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding='utf-8')
            func_log.info(f"Successfully wrote {len(content)} characters to '{file_path}'.")
            return f"Successfully wrote content to '{file_path}'."
        except Exception as e:
            func_log.error(f"Failed to write to file: {e}")
            return f"Error writing to file '{file_path}': {e}"

    async def delete_file(self, file_path: str) -> str:
        """Deletes a local file using Python's os module."""
        func_log = log.bind(function_name="delete_file", params={"file_path": file_path})
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                func_log.info(f"Successfully deleted file '{file_path}'.")
                return f"Successfully deleted '{file_path}'."
            else:
                func_log.warning(f"File not found, nothing to delete.")
                return f"File '{file_path}' did not exist."
        except Exception as e:
            func_log.error(f"Failed to delete file: {e}")
            return f"Error deleting file '{file_path}': {e}"

    async def press_key_native(self, key: str, modifier: str = "", app_name: Optional[str] = None) -> str:
        target_app = app_name or self.default_target_app
        if not target_app:
            return "Error: No target application specified."
        func_log = log.bind(function_name="press_key_native", params={"key": key, "modifier": modifier, "target_app": target_app})
        if sys.platform != "darwin":
            return "Error: This skill is only supported on macOS."
        key = key.lower().strip()
        modifier = modifier.lower().strip()
        allowed_keys = ["enter", "return", "tab", "space", "escape"]
        if key not in allowed_keys and (len(key) != 1 or not key.isalnum()):
            return f"Error: Invalid 'key' argument '{key}'."
        allowed_mods = ["", "command", "control", "option", "shift", "alt"]
        if modifier not in allowed_mods:
            return f"Error: Invalid 'modifier' argument '{modifier}'."
        script_command = ""
        if key in ["enter", "return"]:
            script_command = "key code 36"
        else:
            mod_script = f'using {{{modifier if modifier != "alt" else "option"} down}}' if modifier else ""
            script_command = f'keystroke "{key}" {mod_script}'
        full_script = f'tell application "{target_app}" to activate\ndelay 0.2\ntell application "System Events" to {script_command}'
        try:
            func_log.info("Executing native key press...")
            subprocess.run(["osascript", "-e", full_script], check=True, capture_output=True, text=True)
            return f"Successfully pressed '{key}' with modifier '{modifier}' in '{target_app}'."
        except subprocess.CalledProcessError as e:
            func_log.error("AppleScript execution failed", stderr=e.stderr)
            return f"Error executing AppleScript: {e.stderr}"

    async def type_text_native(self, text: str, app_name: Optional[str] = None) -> str:
        target_app = app_name or self.default_target_app
        if not target_app:
            return "Error: No target application specified."
        func_log = log.bind(function_name="type_text_native", params={"target_app": target_app})
        if sys.platform != "darwin":
            return "Error: This skill is only supported on macOS."
        sanitized_text = text.replace('\\', '\\\\').replace('"', '\\"')
        script = f'tell application "System Events" to keystroke "{sanitized_text}"'
        full_script = f'tell application "{target_app}" to activate\ndelay 0.5\n{script}'
        try:
            func_log.info("Executing native typing...")
            subprocess.run(["osascript", "-e", full_script], check=True, capture_output=True, text=True)
            return f"Successfully typed text into '{target_app}'."
        except subprocess.CalledProcessError as e:
            func_log.error("AppleScript execution failed", stderr=e.stderr)
            return f"Error executing AppleScript: {e.stderr}"

    async def read_screen_content(self) -> str:
        func_log = log.bind(function_name="read_screen_content")
        if sys.platform != "darwin":
            return "Error: This skill is only supported on macOS."
        try:
            debug_dir = "debug_screenshots"
            os.makedirs(debug_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join(debug_dir, f"ocr_capture_{timestamp}.png")
            subprocess.run(["screencapture", "-x", screenshot_path], check=True)
            ocr_script_path = os.path.join("scripts", "mac_ocr.swift")
            if not os.path.exists(ocr_script_path):
                return f"Error: OCR script not found at '{ocr_script_path}'"
            process = subprocess.run(["swift", ocr_script_path, screenshot_path], check=True, capture_output=True, text=True)
            extracted_text = process.stdout.strip()
            func_log.info(f"Successfully extracted {len(extracted_text)} chars from screen.")
            return extracted_text
        except subprocess.CalledProcessError as e:
            func_log.error("Screen reading failed", stderr=e.stderr)
            return f"Error during screen reading: {e.stderr}"