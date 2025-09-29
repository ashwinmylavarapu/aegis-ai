# src/aegis/adapters/outbound/apple_script_os_adapter.py
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime
from loguru import logger
from typing import Dict, Any, Optional, List
import asyncio
import re
import json
import stat

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

    async def list_windows(self, app_name: str) -> List[str]:
        """Lists the titles of all open windows for a given application."""
        func_log = log.bind(function_name="list_windows", params={"app_name": app_name})
        script = f'tell application "System Events" to get name of every window of process "{app_name}"'
        try:
            func_log.info(f"Listing windows for '{app_name}'...")
            result = subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
            window_list = [name.strip() for name in result.stdout.strip().split(',') if name.strip()]
            func_log.info(f"Found windows: {window_list}")
            return window_list
        except subprocess.CalledProcessError as e:
            func_log.error("Failed to list windows", stderr=e.stderr)
            return []

    async def focus_window(self, app_name: str, window_title: str) -> str:
        """Brings a specific window of an application to the foreground."""
        func_log = log.bind(function_name="focus_window", params={"app_name": app_name, "window_title": window_title})
        await self._capture_desktop_evidence(f"focus_window_{app_name}", "before")
        script = f'tell application "System Events" to perform action "AXRaise" of window "{window_title}" of process "{app_name}"'
        try:
            func_log.info(f"Focusing window '{window_title}' for app '{app_name}'...")
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
            await self._capture_desktop_evidence(f"focus_window_{app_name}", "after")
            return f"Successfully focused on window '{window_title}'."
        except subprocess.CalledProcessError as e:
            func_log.error("Failed to focus window", stderr=e.stderr)
            await self._capture_desktop_evidence(f"focus_window_{app_name}", "error")
            return f"Error focusing window '{window_title}': {e.stderr}"

    async def get_window_bounds(self, app_name: str, window_title: str) -> Dict[str, int]:
        """Gets the position and size of a specific window."""
        func_log = log.bind(function_name="get_window_bounds", params={"app_name": app_name, "window_title": window_title})
        script = f'tell application "System Events" to get {{position, size}} of window "{window_title}" of process "{app_name}"'
        try:
            result = subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
            nums = [int(n) for n in re.findall(r'-?\d+', result.stdout)]
            bounds = {"x": nums[0], "y": nums[1], "width": nums[2], "height": nums[3]}
            func_log.info(f"Got window bounds: {bounds}")
            return bounds
        except (subprocess.CalledProcessError, IndexError, ValueError) as e:
            func_log.error("Failed to get window bounds", error=str(e))
            return {}

    async def set_window_bounds(self, app_name: str, window_title: str, x: Optional[int] = None, y: Optional[int] = None, width: Optional[int] = None, height: Optional[int] = None) -> str:
        """Moves and/or resizes a specific window."""
        func_log = log.bind(function_name="set_window_bounds", params={"app_name": app_name, "window_title": window_title, "x": x, "y": y, "width": width, "height": height})
        await self._capture_desktop_evidence(f"set_bounds_{app_name}", "before")
        scripts = []
        if x is not None and y is not None:
            scripts.append(f'set position of window "{window_title}" of process "{app_name}" to {{{x}, {y}}}')
        if width is not None and height is not None:
            scripts.append(f'set size of window "{window_title}" of process "{app_name}" to {{{width}, {height}}}')
        if not scripts:
            return "No position or size parameters provided; no action taken."
        full_script = f'tell application "System Events"\n' + "\n".join(scripts) + f'\nend tell'
        try:
            func_log.info(f"Setting bounds for window '{window_title}'...")
            subprocess.run(["osascript", "-e", full_script], check=True, capture_output=True, text=True)
            await self._capture_desktop_evidence(f"set_bounds_{app_name}", "after")
            return f"Successfully set bounds for window '{window_title}'."
        except subprocess.CalledProcessError as e:
            func_log.error("Failed to set window bounds", stderr=e.stderr)
            await self._capture_desktop_evidence(f"set_bounds_{app_name}", "error")
            return f"Error setting window bounds: {e.stderr}"

    async def write_file(self, file_path: str, content: str, executable: bool = False) -> str:
        """Writes content to a local file, optionally making it executable."""
        func_log = log.bind(function_name="write_file", params={"file_path": file_path, "executable": executable})
        try:
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding='utf-8')
            
            if executable:
                func_log.info(f"Making file executable: {file_path}")
                # Set permissions to rwxr-xr-x (0o755)
                os.chmod(file_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

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

    async def read_clipboard(self) -> str:
        """Reads the current text content from the system clipboard."""
        func_log = log.bind(function_name="read_clipboard")
        if sys.platform != "darwin":
            return "Error: This skill is only supported on macOS."
        try:
            func_log.info("Reading from clipboard...")
            script = "the clipboard"
            process = subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
            content = process.stdout.strip()
            func_log.success(f"Successfully read {len(content)} characters from clipboard.")
            return content
        except subprocess.CalledProcessError as e:
            func_log.error("Failed to read from clipboard", stderr=e.stderr)
            return f"Error reading from clipboard: {e.stderr}"

    async def write_clipboard(self, text: str) -> str:
        """Writes text content to the system clipboard."""
        func_log = log.bind(function_name="write_clipboard")
        if sys.platform != "darwin":
            return "Error: This skill is only supported on macOS."
        try:
            func_log.info(f"Writing {len(text)} characters to clipboard...")
            script = f'set the clipboard to "{text}"'
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
            func_log.success("Successfully wrote to clipboard.")
            return "Successfully wrote text to clipboard."
        except subprocess.CalledProcessError as e:
            func_log.error("Failed to write to clipboard", stderr=e.stderr)
            return f"Error writing to clipboard: {e.stderr}"

    async def run_script(self, script_path: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """Executes a local script and returns its output."""
        func_log = log.bind(function_name="run_script", params={"script_path": script_path, "args": args})
        if not os.path.exists(script_path):
            return {"error": f"Script not found at '{script_path}'"}
        
        command = [script_path] + (args or [])
        try:
            func_log.info(f"Executing script: {' '.join(command)}")
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            
            result = {
                "return_code": process.returncode,
                "stdout": stdout.decode('utf-8').strip(),
                "stderr": stderr.decode('utf-8').strip(),
            }
            func_log.info(f"Script finished with return code {result['return_code']}.")
            return result
        except Exception as e:
            func_log.error(f"Failed to run script: {e}")
            return {"error": str(e)}

    @classmethod
    def get_tools(cls) -> List[dict]:
        """Returns a list of tool definitions for the adapter."""
        return [
            {"name": "launch_app", "description": "Launches a native application, optionally opening a file.", "parameters": {"type": "OBJECT", "properties": {"app_name": {"type": "STRING"}, "file_path": {"type": "STRING"}}, "required": ["app_name"]}},
            {"name": "quit_app", "description": "Quits a native application.", "parameters": {"type": "OBJECT", "properties": {"app_name": {"type": "STRING"}}, "required": ["app_name"]}},
            {"name": "list_windows", "description": "Lists the titles of all open windows for a given application.", "parameters": {"type": "OBJECT", "properties": {"app_name": {"type": "STRING"}}, "required": ["app_name"]}},
            {"name": "focus_window", "description": "Brings a specific window of an application to the foreground.", "parameters": {"type": "OBJECT", "properties": {"app_name": {"type": "STRING"}, "window_title": {"type": "STRING"}}, "required": ["app_name", "window_title"]}},
            {"name": "get_window_bounds", "description": "Gets the position and size of a specific window.", "parameters": {"type": "OBJECT", "properties": {"app_name": {"type": "STRING"}, "window_title": {"type": "STRING"}}, "required": ["app_name", "window_title"]}},
            {"name": "set_window_bounds", "description": "Moves and/or resizes a specific window.", "parameters": {"type": "OBJECT", "properties": {"app_name": {"type": "STRING"}, "window_title": {"type": "STRING"}, "x": {"type": "INTEGER"}, "y": {"type": "INTEGER"}, "width": {"type": "INTEGER"}, "height": {"type": "INTEGER"}}, "required": ["app_name", "window_title"]}},
            {"name": "write_file", "description": "Writes content to a local file, optionally making it executable.", "parameters": {"type": "OBJECT", "properties": {"file_path": {"type": "STRING"}, "content": {"type": "STRING"}, "executable": {"type": "BOOLEAN"}}, "required": ["file_path", "content"]}},
            {"name": "delete_file", "description": "Deletes a local file.", "parameters": {"type": "OBJECT", "properties": {"file_path": {"type": "STRING"}}, "required": ["file_path"]}},
            {"name": "press_key_native", "description": "Presses a key or key combination at the OS level.", "parameters": {"type": "OBJECT", "properties": {"key": {"type": "STRING"}, "modifier": {"type": "STRING"}, "app_name": {"type": "STRING"}}, "required": ["key"]}},
            {"name": "type_text_native", "description": "Types a string of text at the OS level.", "parameters": {"type": "OBJECT", "properties": {"text": {"type": "STRING"}, "app_name": {"type": "STRING"}}, "required": ["text"]}},
            {"name": "read_screen_content", "description": "Captures the screen and uses OCR to extract all visible text.", "parameters": {"type": "OBJECT", "properties": {}, "required": []}},
            {"name": "read_clipboard", "description": "Reads the current text content from the system clipboard.", "parameters": {"type": "OBJECT", "properties": {}, "required": []}},
            {"name": "write_clipboard", "description": "Writes text content to the system clipboard.", "parameters": {"type": "OBJECT", "properties": {"text": {"type": "STRING"}}, "required": ["text"]}},
            {"name": "run_script", "description": "Executes a local script and returns its output.", "parameters": {"type": "OBJECT", "properties": {"script_path": {"type": "STRING"}, "args": {"type": "ARRAY", "items": {"type": "STRING"}}}, "required": ["script_path"]}},
        ]