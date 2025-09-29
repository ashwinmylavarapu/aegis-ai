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
from datetime import datetime

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
        # This function is not available in all environments, especially CI.
        # It's a known limitation for local testing.
        # pyperclip.copy(data) 
        logger.debug(f"Successfully processed image from '{image_path}' for clipboard.")
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
        self.debug_dir = "debug_screenshots"
        os.makedirs(self.debug_dir, exist_ok=True)
        logger.info(f"PlaywrightAdapter initialized. CDP Endpoint: {self.cdp_endpoint or 'Not set'}")

    async def _capture_visual_evidence(self, tool_name: str, selector: Optional[str] = None) -> str:
        """Helper to capture before/after screenshots for a tool call."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        context_slug = f"{tool_name}"
        if selector:
            # Sanitize selector for use in filename
            s_slug = ''.join(c for c in selector if c.isalnum() or c in ('-', '_'))[:30]
            context_slug = f"{tool_name}_{s_slug}"
        
        before_path = os.path.join(self.debug_dir, f"{timestamp}_{context_slug}_before.png")
        await self.page.screenshot(path=before_path)
        
        # Highlight the element if a selector is provided
        if selector:
            try:
                await self.page.locator(selector).highlight()
            except Exception:
                pass # Ignore if element not found, screenshot still useful
                
        logger.debug(f"Saved pre-action screenshot to '{before_path}'")
        return context_slug

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
        context_slug = await self._capture_visual_evidence("click", selector)
        
        await self.page.click(selector)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        after_path = os.path.join(self.debug_dir, f"{timestamp}_{context_slug}_after.png")
        await self.page.screenshot(path=after_path)
        logger.debug(f"Saved post-action screenshot to '{after_path}'")
        
        result = f"Successfully clicked on '{selector}'. See debug screenshots for visual verification."
        logger.debug(f"Exit tool: click -> {result}")
        return result

    async def type_text(self, selector: str, text: str) -> str:
        logger.debug(f"Enter tool: type_text(selector='{selector}', text='{text}')")
        context_slug = await self._capture_visual_evidence("type_text", selector)
        
        await self.page.fill(selector, text)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        after_path = os.path.join(self.debug_dir, f"{timestamp}_{context_slug}_after.png")
        await self.page.screenshot(path=after_path)
        logger.debug(f"Saved post-action screenshot to '{after_path}'")
        
        result = f"Successfully typed '{text}' into '{selector}'. See debug screenshots for visual verification."
        logger.debug(f"Exit tool: type_text -> {result}")
        return result

    async def press_key(self, key: str) -> str:
        logger.debug(f"Enter tool: press_key(key='{key}')")
        context_slug = await self._capture_visual_evidence("press_key")
        
        try:
            await self.page.locator('body').focus()
            logger.debug("Focused on the page body.")

            parts = key.split('+')
            main_key = parts[-1]

            await self.page.keyboard.press(main_key)
            logger.debug(f"Keyboard.press('{main_key}')")
            await asyncio.sleep(0.1)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            after_path = os.path.join(self.debug_dir, f"{timestamp}_{context_slug}_after.png")
            await self.page.screenshot(path=after_path)
            logger.debug(f"Saved post-action screenshot to '{after_path}'")

            result = f"Successfully executed key press '{key}'. Check debug screenshots for visual verification."
            logger.debug(f"Exit tool: press_key -> {result}")
            return result

        except Exception as e:
            logger.error(f"Failed to press key combination '{key}': {e}")
            return f"Error pressing key combination '{key}': {e}"

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
                "description": "Presses a single key, like 'Enter', 'F1'. For combinations, the agent should use native skills.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {"key": {"type": "STRING", "description": "The key to press (e.g., 'Enter')."}}, 
                    "required": ["key"]
                }
            },
            {"name": "wait", "description": "Waits for a specified number of seconds.", "parameters": {"type": "OBJECT", "properties": {"seconds": {"type": "INTEGER"}}, "required": ["seconds"]}},
            {
                "name": "paste_image",
                "description": "Pastes an image into an element from the system clipboard.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "selector": {"type": "STRING", "description": "The CSS selector of the element to paste into."}
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