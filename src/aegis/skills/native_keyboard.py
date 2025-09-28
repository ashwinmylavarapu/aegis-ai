# src/aegis/skills/native_keyboard.py
import subprocess
import sys
from loguru import logger
import asyncio

# Bind a logger with skill-specific context for structured logging
log = logger.bind(skill_name="native_keyboard")

async def press_key_native(key: str, modifier: str = "") -> str:
    """
    Brings the target application to the front and presses a key or key combination at the OS level using AppleScript.
    This skill is security-sensitive and performs strict input validation.
    """
    func_log = log.bind(function_name="press_key_native", params={"key": key, "modifier": modifier})

    if sys.platform != "darwin":
        func_log.error("Unsupported OS for native key press.")
        return "Error: Native key press is only supported on macOS."

    key = key.lower().strip()
    modifier = modifier.lower().strip()
    
    # --- SECURITY: Stricter input validation to prevent injection ---
    allowed_special_keys = ["enter", "return", "tab", "space", "escape"]
    if key not in allowed_special_keys and (len(key) != 1 or not key.isalnum()):
        error_msg = f"Invalid 'key' argument: '{key}'. Must be in allow-list or a single alphanumeric char."
        func_log.warning(error_msg)
        return f"Error: {error_msg}"

    allowed_modifiers = ["", "command", "control", "option", "shift", "alt"]
    if modifier not in allowed_modifiers:
        error_msg = f"Invalid 'modifier' argument: '{modifier}'. Must be one of {allowed_modifiers}."
        func_log.warning(error_msg)
        return f"Error: {error_msg}"
    
    script_command = ""
    if key in ["enter", "return"]:
        script_command = "key code 36"
    else:
        # Use double quotes for keystroke, which is the correct AppleScript string literal
        if modifier:
            if modifier == "alt": modifier = "option"
            script_command = f'keystroke "{key}" using {{{modifier} down}}'
        else:
            script_command = f'keystroke "{key}"'
    
    full_script = f'tell application "Comet" to activate\ndelay 0.2\ntell application "System Events" to {script_command}'
    
    try:
        func_log.info(f"Executing native key press...")
        func_log.debug(f"AppleScript command: {full_script}")
        process = subprocess.run(["osascript", "-e", full_script], check=True, capture_output=True, text=True)
        result = f"Successfully pressed '{key}' natively."
        func_log.info(result, stdout=process.stdout)
        return result
    except subprocess.CalledProcessError as e:
        error_msg = f"AppleScript execution failed."
        func_log.error(error_msg, stderr=e.stderr)
        return f"{error_msg} Stderr: {e.stderr}"
    except Exception as e:
        func_log.exception("An unexpected error occurred during native key press.")
        return f"An unexpected error occurred: {e}"

async def type_text_native(text: str) -> str:
    """
    Brings the target application to the front and types a string of text at the OS level using AppleScript.
    """
    func_log = log.bind(function_name="type_text_native", params={"text": text[:20] + "..."})

    if sys.platform != "darwin":
        func_log.error("Unsupported OS for native typing.")
        return "Error: Native typing is only supported on macOS."

    sanitized_text = text.replace('\\', '\\\\').replace('"', '\\"')
    
    script = f'tell application "System Events" to keystroke "{sanitized_text}"'
    full_script = f'tell application "Comet" to activate\ndelay 0.5\n{script}'
    
    try:
        func_log.info(f"Executing native typing...")
        func_log.debug(f"AppleScript command: {full_script}")
        process = subprocess.run(["osascript", "-e", full_script], check=True, capture_output=True, text=True)
        result = f"Successfully typed text natively."
        func_log.info(result, stdout=process.stdout)
        return result
    except subprocess.CalledProcessError as e:
        error_msg = f"AppleScript execution failed."
        func_log.error(error_msg, stderr=e.stderr)
        return f"{error_msg} Stderr: {e.stderr}"
    except Exception as e:
        func_log.exception("An unexpected error occurred during native typing.")
        return f"An unexpected error occurred: {e}"