# src/aegis/skills/native_screen_reader.py
import subprocess
import sys
from loguru import logger
import os
import tempfile
from datetime import datetime

# Bind a logger with skill-specific context for structured logging
log = logger.bind(skill_name="native_screen_reader")

async def read_screen_content() -> str:
    """
    Captures the screen, saves it as a debug artifact, and uses OCR to extract all visible text.
    """
    func_log = log.bind(function_name="read_screen_content")
    
    if sys.platform != "darwin":
        func_log.error("Unsupported OS for native screen reading.")
        return "Error: Native screen reading is only supported on macOS."

    screenshot_path = ""
    try:
        # --- OBSERVABILITY: Save screenshot as a debug artifact ---
        debug_dir = "debug_screenshots"
        os.makedirs(debug_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = os.path.join(debug_dir, f"ocr_capture_{timestamp}.png")
        
        func_log.info(f"Capturing screen to debug artifact: {screenshot_path}")
        subprocess.run(["screencapture", "-x", screenshot_path], check=True)
        
        ocr_script_path = os.path.join("scripts", "mac_ocr.swift")
        if not os.path.exists(ocr_script_path):
            func_log.error(f"OCR script not found.", script_path=ocr_script_path)
            return f"Error: OCR script not found at '{ocr_script_path}'"
            
        func_log.info("Performing OCR on the screenshot...")
        # In a production system, a tracing span would start here.
        process = subprocess.run(
            ["swift", ocr_script_path, screenshot_path],
            check=True,
            capture_output=True,
            text=True,
        )
        
        extracted_text = process.stdout.strip()
        func_log.info(f"Successfully extracted text from screen.", text_length=len(extracted_text))
        func_log.debug(f"Extracted Text Snippet: {extracted_text[:200]}...")
        
        # In a production system, a metric for success would be incremented here.
        return extracted_text

    except subprocess.CalledProcessError as e:
        error_msg = f"Screen reading failed."
        func_log.error(error_msg, stderr=e.stderr, screenshot_path=screenshot_path)
        # In a production system, a metric for failure would be incremented here.
        return f"{error_msg} Stderr: {e.stderr}"
    except Exception as e:
        func_log.exception("An unexpected error occurred during screen reading.", screenshot_path=screenshot_path)
        return f"An unexpected error occurred: {e}"