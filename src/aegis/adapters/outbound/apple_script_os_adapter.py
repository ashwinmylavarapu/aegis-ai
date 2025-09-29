# src/aegis/adapters/outbound/apple_script_os_adapter.py
import subprocess
import sys
import os
import tempfile
from datetime import datetime
from loguru import logger
from typing import Dict, Any

from .native_os_adapter import NativeOSAdapter

log = logger.bind(adapter_name="AppleScriptOSAdapter")

class AppleScriptOSAdapter(NativeOSAdapter):
    """An adapter for native macOS interactions using AppleScript."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config.get("native_os", {})
        self.target_app = self.config.get("target_app")
        if not self.target_app:
            raise ValueError("native_os.target_app is not set in config.yaml")
        log.info(f"Initialized with target_app: '{self.target_app}'")

    async def press_key_native(self, key: str, modifier: str = "") -> str:
        """Brings the target application to the front and presses a key."""
        func_log = log.bind(function_name="press_key_native", params={"key": key, "modifier": modifier})

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

        full_script = f'tell application "{self.target_app}" to activate\ndelay 0.2\ntell application "System Events" to {script_command}'
        
        try:
            func_log.info("Executing native key press...")
            process = subprocess.run(["osascript", "-e", full_script], check=True, capture_output=True, text=True)
            return f"Successfully pressed '{key}' with modifier '{modifier}' in '{self.target_app}'."
        except subprocess.CalledProcessError as e:
            func_log.error("AppleScript execution failed", stderr=e.stderr)
            return f"Error executing AppleScript: {e.stderr}"

    async def type_text_native(self, text: str) -> str:
        """Brings the target application to the front and types text."""
        func_log = log.bind(function_name="type_text_native")

        if sys.platform != "darwin":
            return "Error: This skill is only supported on macOS."

        sanitized_text = text.replace('\\', '\\\\').replace('"', '\\"')
        script = f'tell application "System Events" to keystroke "{sanitized_text}"'
        full_script = f'tell application "{self.target_app}" to activate\ndelay 0.5\n{script}'

        try:
            func_log.info("Executing native typing...")
            process = subprocess.run(["osascript", "-e", full_script], check=True, capture_output=True, text=True)
            return f"Successfully typed text into '{self.target_app}'."
        except subprocess.CalledProcessError as e:
            func_log.error("AppleScript execution failed", stderr=e.stderr)
            return f"Error executing AppleScript: {e.stderr}"

    async def read_screen_content(self) -> str:
        """Captures the screen and performs OCR."""
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