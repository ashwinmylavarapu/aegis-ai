# src/aegis/skills/native_keyboard.py
import subprocess
import sys
from loguru import logger
import asyncio

async def press_key_native(key: str, modifier: str = "") -> str:
    """
    Brings the target application to the front and presses a key or key combination at the OS level using AppleScript.
    Required for triggering browser extension shortcuts or submitting forms.
    """
    if sys.platform != "darwin":
        return "Error: Native key press is only supported on macOS."

    key = key.lower().strip()
    modifier = modifier.lower().strip()
    
    script_command = ""

    # --- START: KEY CODE FIX ---
    # Check for special keys that require 'key code' instead of 'keystroke'
    if key in ["enter", "return"]:
        # 'key code 36' is the correct command for the Return/Enter key.
        script_command = "key code 36"
    else:
        # For all other single characters and modifier combinations
        if modifier:
            if modifier == "alt": modifier = "option"
            script_command = f'keystroke "{key}" using {{{modifier} down}}'
        else:
            script_command = f'keystroke "{key}"'
    # --- END: KEY CODE FIX ---
    
    # This robust script ensures the target app is frontmost before sending the keystroke.
    full_script = f'''
    tell application "Comet" to activate
    delay 0.2
    tell application "System Events" to {script_command}
    '''
    
    try:
        logger.info(f"Executing native key press via AppleScript...")
        subprocess.run(["osascript", "-e", full_script], check=True, capture_output=True, text=True)
        result = f"Successfully pressed '{key}' natively."
        logger.info(result)
        return result
    except subprocess.CalledProcessError as e:
        error_msg = f"AppleScript execution failed. Stderr: {e.stderr}"
        logger.error(error_msg)
        return error_msg
    except Exception as e:
        logger.error(f"An unexpected error occurred during native key press: {e}")
        return f"An unexpected error occurred: {e}"

async def type_text_native(text: str) -> str:
    """
    Brings the target application to the front and types a string of text at the OS level using AppleScript.
    """
    if sys.platform != "darwin":
        return "Error: Native typing is only supported on macOS."

    # Escape double quotes in the text for AppleScript
    sanitized_text = text.replace('"', '\\"')
    
    script = f'tell application "System Events" to keystroke "{sanitized_text}"'

    full_script = f'''
    tell application "Comet" to activate
    delay 0.5
    {script}
    '''
    
    try:
        logger.info(f"Executing native typing via AppleScript...")
        subprocess.run(["osascript", "-e", full_script], check=True, capture_output=True, text=True)
        result = f"Successfully typed text natively: '{text}'"
        logger.info(result)
        return result
    except subprocess.CalledProcessError as e:
        error_msg = f"AppleScript execution failed. Stderr: {e.stderr}"
        logger.error(error_msg)
        return error_msg
    except Exception as e:
        logger.error(f"An unexpected error occurred during native typing: {e}")
        return f"An unexpected error occurred: {e}"