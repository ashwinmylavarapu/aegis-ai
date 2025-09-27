# src/aegis/adapters/outbound/playwright_adapter.py
from typing import List, Dict, Any, Optional
import asyncio
import sys
from loguru import logger
from playwright.async_api import async_playwright
import pyperclip
from PIL import Image
import io
import os

from .base import OutboundAdapter

# Helper function to copy image to clipboard, required for paste_image
def copy_image_to_clipboard(image_path: str):
    """Reads an image file and copies it to the system clipboard."""
    try:
        image = Image.open(image_path)
        output = io.BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]
        output.close()
        pyperclip.copy(data)
        logger.debug(f"Successfully copied image from '{image_path}' to clipboard.")
        return True
    except Exception as e:
        logger.error(f"Failed to copy image to clipboard: {e}")
        return False

class PlaywrightAdapter(OutboundAdapter):
    def __init__(self, config: Dict[str, Any]):
        browser_config = config.get("browser", {}).get("playwright", {})
        self.cdp_endpoint = browser_config.get("cdp_endpoint")
        self.browser = None
        self.page = None
        logger.info(f"PlaywrightAdapter initialized. CDP Endpoint: {self.cdp_endpoint or 'Not set'}")

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        if self.cdp_endpoint:
            logger.debug(f"Attempting to connect to existing browser via CDP: {self.cdp_endpoint}")
            self.browser = await self.playwright.chromium.connect_over_cdp(self.cdp_endpoint)
            context = self.browser.contexts[0] if self.browser.contexts else await self.browser.new_context()
            self.page = context.pages[0] if context.pages else await context.new_page()
            logger.debug("Successfully connected to browser and got a page object.")
        else:
            logger.debug("No CDP endpoint set. Launching a new browser instance.")
            self.browser = await self.playwright.chromium.launch(headless=False)
            self.page = await self.browser.new_page()
            logger.debug("New browser instance launched.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if not self.cdp_endpoint and self.browser:
            logger.debug("Closing browser instance that was launched by this adapter.")
            await self.browser.close()
        if self.playwright:
            logger.debug("Stopping Playwright.")
            await self.playwright.stop()

    async def navigate(self, url: str) -> str:
        logger.debug(f"Enter tool: navigate(url='{url}')")
        await self.page.goto(url)
        result = f"Successfully navigated to {url}"
        logger.debug(f"Exit tool: navigate -> {result}")
        return result

    async def click(self, selector: str) -> str:
        logger.debug(f"Enter tool: click(selector='{selector}')")
        await self.page.click(selector)
        result = f"Successfully clicked on element with selector: {selector}"
        logger.debug(f"Exit tool: click -> {result}")
        return result

    async def type_text(self, selector: str, text: str) -> str:
        logger.debug(f"Enter tool: type_text(selector='{selector}', text='{text}')")
        await self.page.fill(selector, text)
        result = f"Successfully typed '{text}' into element with selector: {selector}"
        logger.debug(f"Exit tool: type_text -> {result}")
        return result

    async def press_key(self, key: str) -> str:
        # --- START: DEBUGGING & OBSERVABILITY LOGIC ---
        logger.debug(f"Enter tool: press_key(key='{key}')")
        
        try:
            debug_dir = "debug_screenshots"
            os.makedirs(debug_dir, exist_ok=True)
            
            # 1. VISUAL EVIDENCE (BEFORE): See the state before the action.
            before_path = os.path.join(debug_dir, "debug_before_keypress.png")
            await self.page.screenshot(path=before_path)
            logger.debug(f"Saved pre-action screenshot to '{before_path}'")

            await self.page.locator('body').focus()
            logger.debug("Focused on the page body.")

            parts = key.split('+')
            modifiers = [part for part in parts[:-1] if part in ['Control', 'Alt', 'Shift', 'Meta']]
            main_key = parts[-1]

            for modifier in modifiers:
                await self.page.keyboard.down(modifier)
                logger.debug(f"Keyboard.down('{modifier}')")
                await asyncio.sleep(0.1) # Added delay

            await self.page.keyboard.press(main_key)
            logger.debug(f"Keyboard.press('{main_key}')")
            await asyncio.sleep(0.1) # Added delay

            for modifier in reversed(modifiers):
                await self.page.keyboard.up(modifier)
                logger.debug(f"Keyboard.up('{modifier}')")
                await asyncio.sleep(0.1) # Added delay

            # 2. VISUAL EVIDENCE (AFTER): See the state after the action.
            after_path = os.path.join(debug_dir, "debug_after_keypress.png")
            await self.page.screenshot(path=after_path)
            logger.debug(f"Saved post-action screenshot to '{after_path}'")

            result = f"Successfully executed key press '{key}'. Check debug screenshots for visual verification."
            logger.debug(f"Exit tool: press_key -> {result}")
            return result

        except Exception as e:
            logger.error(f"Failed to press key combination '{key}': {e}")
            return f"Error pressing key combination '{key}': {e}"
        # --- END: DEBUGGING & OBSERVABILITY LOGIC ---

    async def wait(self, seconds: int) -> str:
        logger.debug(f"Enter tool: wait(seconds={seconds})")
        await asyncio.sleep(seconds)
        result = f"Waited for {seconds} seconds."
        logger.debug(f"Exit tool: wait -> {result}")
        return result

    async def paste_image(self, selector: str, image_path: Optional[str] = None) -> str:
        logger.debug(f"Enter tool: paste_image(selector='{selector}', image_path='{image_path}')")
        try:
            if image_path:
                logger.debug(f"Image path provided. Reading '{image_path}' to clipboard.")
                if not copy_image_to_clipboard(image_path):
                    raise Exception("Failed to copy image to clipboard.")
            else:
                logger.debug("No image path provided. Pasting directly from clipboard.")

            await self.page.click(selector)
            await self.page.keyboard.press("ControlOrMeta+V")
            result = f"Pasted image into '{selector}'."
            logger.debug(f"Exit tool: paste_image -> {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to paste image: {e}")
            return f"Error pasting image: {e}"

    async def take_screenshot(self, path: str) -> str:
        logger.debug(f"Enter tool: take_screenshot(path='{path}')")
        await self.page.screenshot(path=path)
        result = f"Screenshot saved to {path}"
        logger.debug(f"Exit tool: take_screenshot -> {result}")
        return result

    @classmethod
    def get_tools(cls) -> List[dict]:
        return [
            {"name": "navigate", "description": "Navigates to a URL.", "parameters": {"type": "OBJECT", "properties": {"url": {"type": "STRING"}}, "required": ["url"]}},
            {"name": "click", "description": "Clicks an element by selector.", "parameters": {"type": "OBJECT", "properties": {"selector": {"type": "STRING"}}, "required": ["selector"]}},
            {"name": "type_text", "description": "Types text into an element by selector.", "parameters": {"type": "OBJECT", "properties": {"selector": {"type": "STRING"}, "text": {"type": "STRING"}}, "required": ["selector", "text"]}},
            {
                "name": "press_key",
                "description": "Presses a single key or a combination of keys, like 'Enter', 'F1', 'Control+C', or 'Alt+A'. Handles Mac vs Windows/Linux differences.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {"key": {"type": "STRING", "description": "The key or key combination to press (e.g., 'Alt+A')."}}, 
                    "required": ["key"]
                }
            },
            {"name": "wait", "description": "Waits for a specified number of seconds.", "parameters": {"type": "OBJECT", "properties": {"seconds": {"type": "INTEGER"}}, "required": ["seconds"]}},
            {
                "name": "paste_image",
                "description": "Pastes an image into an element. If image_path is provided, it copies that image to the clipboard first. Otherwise, it pastes from the current clipboard.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "selector": {"type": "STRING", "description": "The CSS selector of the element to paste into."},
                        "image_path": {"type": "STRING", "description": "Optional. The local file path of the image to copy and paste."}
                    },
                    "required": ["selector"]
                },
            },
            {
                "name": "take_screenshot",
                "description": "Takes a screenshot of the current page and saves it to a file.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "path": {"type": "STRING", "description": "The file path to save the screenshot to."}
                    },
                    "required": ["path"]
                }
            }
        ]