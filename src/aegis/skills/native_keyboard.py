# src/aegis/skills/native_keyboard.py
import subprocess
import sys
from loguru import logger
import asyncio

async def press_key_native(key: str, modifier: str = "alt") -> str:
    """
    Brings Google Chrome to the front and presses a key combination at the OS level using AppleScript.
    This is required for triggering browser extension shortcuts.
    """
    if sys.platform != "darwin":
        return "Error: Native key press is only supported on macOS."

    key = key.lower().strip()
    modifier = modifier.lower().strip()
    
    if len(key) != 1 or not key.isalnum():
        return f"Error: Invalid 'key' argument: {key}. Must be a single alphanumeric character."
    
    valid_modifiers = ["command", "control", "option", "shift", "alt"]
    if modifier not in valid_modifiers:
        return f"Error: Invalid 'modifier' argument: {modifier}. Must be one of {valid_modifiers}."

    if modifier == "alt":
        modifier = "option"

    # This robust script ensures Chrome is the frontmost application before sending the keystroke.
    script = f'''
    tell application "Comet" to activate
    delay 0.2
    tell application "System Events" to keystroke "{key}" using {{{modifier} down}}
    '''
    
    try:
        logger.info(f"Executing robust native key press via AppleScript...")
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
        result = f"Successfully activated Chrome and pressed '{modifier}+{key}' natively."
        logger.info(result)
        return result
    except subprocess.CalledProcessError as e:
        error_msg = f"AppleScript execution failed. Stderr: {e.stderr}"
        logger.error(error_msg)
        return error_msg
    except Exception as e:
        logger.error(f"An unexpected error occurred during native key press: {e}")
        return f"An unexpected error occurred: {e}"