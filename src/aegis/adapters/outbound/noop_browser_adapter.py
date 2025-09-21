# src/aegis/adapters/outbound/noop_browser_adapter.py
from typing import List, Dict, Any
from loguru import logger
from .browser_adapter import BrowserAdapter


class NoOpBrowserAdapter(BrowserAdapter):
    """
    A no-operation browser adapter for testing and dry-runs.
    It logs the actions that would be performed without actually interacting with a browser.
    """

    def __init__(self, config: Dict[str, Any] = None):
        logger.info("NoOpBrowserAdapter initialized.")
        self.config = config

    async def __aenter__(self):
        logger.info("NoOpBrowserAdapter context entered.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.info("NoOpBrowserAdapter context exited.")

    async def navigate(self, url: str) -> str:
        logger.info(f"--- NoOpBrowser: Navigating to {url}")
        return f"Navigated to {url}"

    async def get_page_content(self, clean: bool = True) -> str:
        logger.info(f"--- NoOpBrowser: Getting page content (clean={clean})")
        return "<html><body><h1>No-op Page</h1></body></html>"

    async def type_text(self, selector: str, text: str) -> str:
        logger.info(f"--- NoOpBrowser: Typing '{text}' into element '{selector}'")
        return f"Typed '{text}' into '{selector}'"

    async def paste(self, selector: str, text: str) -> str:
        logger.info(f"--- NoOpBrowser: Pasting '{text}' into element '{selector}'")
        return f"Pasted text into '{selector}'"

    async def click(self, selector: str) -> str:
        logger.info(f"--- NoOpBrowser: Clicking on element '{selector}'")
        return f"Clicked '{selector}'"

    async def scroll(self, direction: str) -> str:
        logger.info(f"--- NoOpBrowser: Scrolling {direction}")
        return f"Scrolled {direction}"

    async def wait_for_element(self, selector: str, timeout: int = 10000) -> str:
        logger.info(f"--- NoOpBrowser: Waiting for element '{selector}' for {timeout}ms")
        return f"Waited for '{selector}'"

    async def extract_data(self, selector: str, fields: Dict[str, str], limit: int) -> List[Dict[str, Any]]:
        logger.info(f"--- NoOpBrowser: Extracting data from '{selector}'")
        # Return dummy data that matches the structure
        return [
            {"title": "Dummy Title 1", "team": "Dummy Team 1", "url": "/dummy1"},
            {"title": "Dummy Title 2", "team": "Dummy Team 2", "url": "/dummy2"},
        ]

    async def get_activity_post_details(self, post_selector: str) -> Dict[str, Any]:
        logger.info(f"--- NoOpBrowser: Getting activity post details from '{post_selector}'")
        return {"author": "Dummy Author", "content": "Dummy post content."}

    async def wait(self, seconds: int) -> str:
        logger.info(f"--- NoOpBrowser: Waiting for {seconds} seconds")
        return f"Waited for {seconds} seconds"

    async def paste_image(self, selector: str, image_bytes: bytes) -> str:
        logger.info(f"--- NoOpBrowser: Pasting image into '{selector}'")
        return f"Pasted image into '{selector}'"

    # Adding methods that might be missing from BrowserAdapter but are in PlaywrightAdapter
    # to ensure full compatibility.
    async def take_screenshot(self, path: str) -> str:
        logger.info(f"--- NoOpBrowser: Taking screenshot to {path}")
        return f"Screenshot saved to {path}"

    async def get_html(self) -> str:
        logger.info("--- NoOpBrowser: Getting HTML")
        return "<html></html>"

    async def click_coords(self, x: int, y: int) -> str:
        logger.info(f"--- NoOpBrowser: Clicking at coordinates ({x}, {y})")
        return f"Clicked at ({x}, {y})"

    async def type_text_coords(self, x: int, y: int, text: str) -> str:
        logger.info(f"--- NoOpBrowser: Typing '{text}' at coordinates ({x}, {y})")
        return f"Typed '{text}' at ({x}, {y})"