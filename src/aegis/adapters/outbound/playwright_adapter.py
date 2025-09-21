# src/aegis/adapters/outbound/playwright_adapter.py
from typing import List, Dict, Any, Optional
import asyncio
from loguru import logger
from playwright.async_api import async_playwright
import pyperclip
from PIL import Image
import io

from .base import OutboundAdapter

# Helper function to copy image to clipboard, required for paste_image
def copy_image_to_clipboard(image_path: str):
    """Reads an image file and copies it to the system clipboard."""
    try:
        image = Image.open(image_path)
        output = io.BytesIO()
        # Convert to a format that clipboard understands, e.g., PNG
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]
        output.close()
        # This is a cross-platform way to handle clipboard, but may have OS-level dependencies
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
        logger.debug(f"Enter tool: press_key(key='{key}')")
        await self.page.keyboard.press(key)
        result = f"Successfully pressed the '{key}' key."
        logger.debug(f"Exit tool: press_key -> {result}")
        return result

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
            # Use keyboard shortcuts for robust pasting
            await self.page.keyboard.press("ControlOrMeta+V")
            result = f"Pasted image into '{selector}'."
            logger.debug(f"Exit tool: paste_image -> {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to paste image: {e}")
            return f"Error pasting image: {e}"

    @classmethod
    def get_tools(cls) -> List[dict]:
        """Definitive, complete list of all browser tools available to the agent."""
        return [
            {"name": "navigate", "description": "Navigates to a URL.", "parameters": {"type": "OBJECT", "properties": {"url": {"type": "STRING"}}, "required": ["url"]}},
            {"name": "click", "description": "Clicks an element by selector.", "parameters": {"type": "OBJECT", "properties": {"selector": {"type": "STRING"}}, "required": ["selector"]}},
            {"name": "type_text", "description": "Types text into an element by selector.", "parameters": {"type": "OBJECT", "properties": {"selector": {"type": "STRING"}, "text": {"type": "STRING"}}, "required": ["selector", "text"]}},
            {"name": "press_key", "description": "Presses a key (e.g., 'Enter').", "parameters": {"type": "OBJECT", "properties": {"key": {"type": "STRING"}}, "required": ["key"]}},
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
        ]