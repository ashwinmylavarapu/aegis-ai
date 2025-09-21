# src/aegis/adapters/outbound/playwright_adapter.py
from typing import List, Dict, Any
from loguru import logger
from playwright.async_api import async_playwright

from .base import OutboundAdapter


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
            logger.info(f"Connecting to existing browser via CDP: {self.cdp_endpoint}")
            self.browser = await self.playwright.chromium.connect_over_cdp(self.cdp_endpoint)
            self.page = self.browser.contexts[0].pages[0]
        else:
            logger.info("Launching a new browser instance.")
            self.browser = await self.playwright.chromium.launch(headless=False)
            self.page = await self.browser.new_page()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if not self.cdp_endpoint and self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def navigate(self, url: str):
        logger.info(f"Navigating to {url}")
        await self.page.goto(url)
        return f"Successfully navigated to {url}"

    async def click(self, selector: str):
        logger.info(f"Clicking on element with selector: {selector}")
        await self.page.click(selector)
        return f"Successfully clicked on element with selector: {selector}"

    async def type_text(self, selector: str, text: str):
        logger.info(f"Typing '{text}' into element with selector: {selector}")
        await self.page.fill(selector, text)
        return f"Successfully typed '{text}' into element with selector: {selector}"

    async def get_text(self, selector: str) -> str:
        logger.info(f"Getting text from element with selector: {selector}")
        text = await self.page.text_content(selector)
        return text

    async def take_screenshot(self, path: str):
        logger.info(f"Taking screenshot and saving to {path}")
        await self.page.screenshot(path=path)
        return f"Screenshot saved to {path}"

    async def get_html(self) -> str:
        logger.info("Getting HTML content of the page")
        html = await self.page.content()
        return html

    async def click_coords(self, x: int, y: int):
        logger.info(f"Clicking at coordinates: ({x}, {y})")
        await self.page.mouse.click(x, y)
        return f"Successfully clicked at coordinates ({x}, {y})."

    async def type_text_coords(self, x: int, y: int, text: str):
        logger.info(f"Typing '{text}' at coordinates: ({x}, {y})")
        await self.page.mouse.click(x, y)
        await self.page.keyboard.type(text)
        return f"Successfully typed '{text}' at coordinates ({x}, {y})."

    async def press_key(self, key: str):
        """Simulates a single key press on the keyboard (e.g., 'Enter', 'ArrowDown')."""
        logger.info(f"Pressing key: '{key}'")
        await self.page.keyboard.press(key)
        return f"Successfully pressed the '{key}' key."

    @classmethod
    def get_tools(cls) -> List[dict]:
        return [
            {
                "name": "navigate",
                "description": "Navigates the browser to a specified URL.",
                "parameters": {"type": "OBJECT", "properties": {"url": {"type": "STRING"}}, "required": ["url"]},
            },
            {
                "name": "click",
                "description": "Clicks on an element specified by a CSS selector.",
                "parameters": {"type": "OBJECT", "properties": {"selector": {"type": "STRING"}}, "required": ["selector"]},
            },
            {
                "name": "type_text",
                "description": "Types text into an element specified by a CSS selector.",
                "parameters": {"type": "OBJECT", "properties": {"selector": {"type": "STRING"}, "text": {"type": "STRING"}}, "required": ["selector", "text"]},
            },
            {
                "name": "click_coords",
                "description": "Clicks on a specific (x, y) coordinate.",
                "parameters": {"type": "OBJECT", "properties": {"x": {"type": "INTEGER"}, "y": {"type": "INTEGER"}}, "required": ["x", "y"]},
            },
            {
                "name": "type_text_coords",
                "description": "Types text at a specific (x, y) coordinate.",
                "parameters": {"type": "OBJECT", "properties": {"x": {"type": "INTEGER"}, "y": {"type": "INTEGER"}, "text": {"type": "STRING"}}, "required": ["x", "y", "text"]},
            },
            {
                "name": "press_key",
                "description": "Simulates a single key press on the keyboard (e.g., 'Enter').",
                "parameters": {"type": "OBJECT", "properties": {"key": {"type": "STRING", "description": "The key to press, e.g., 'Enter', 'ArrowDown'."}}, "required": ["key"]},
            },
        ]