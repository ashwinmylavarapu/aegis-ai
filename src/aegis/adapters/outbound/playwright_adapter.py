import asyncio
from typing import Dict, Any, List, Optional
from loguru import logger
from playwright.async_api import async_playwright, Browser, Page, Playwright
from bs4 import BeautifulSoup

from .browser_adapter import BrowserAdapter

class PlaywrightAdapter(BrowserAdapter):
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get("browser", {}).get("playwright", {})
        self.cdp_endpoint = self.config.get("cdp_endpoint")
        if not self.cdp_endpoint:
            raise ValueError("Playwright config missing 'cdp_endpoint' in config.yaml")
        self._playwright: Playwright = None
        self._browser: Browser = None
        self._page: Page = None
        self.is_connected = False

    async def connect(self):
        if self.is_connected: return
        logger.info(f"Connecting to browser at CDP endpoint: {self.cdp_endpoint}")
        self._playwright = await async_playwright().start()
        try:
            self._browser = await self._playwright.chromium.connect_over_cdp(self.cdp_endpoint)
            self._page = self._browser.contexts[0].pages[0] if self._browser.contexts else await (await self._browser.new_context()).new_page()
            self.is_connected = True
            logger.success("Successfully connected to browser.")
        except Exception as e:
            logger.error(f"Failed to connect to browser over CDP: {e}")
            await self.close()
            raise

    async def close(self):
        if self._browser and self._browser.is_connected(): await self._browser.close()
        if self._playwright: await self._playwright.stop()
        self._browser, self._page, self._playwright, self.is_connected = None, None, None, False
        logger.info("Playwright connection closed.")

    async def get_page_content(self) -> str:
        await self.connect()
        logger.info("[BROWSER] Getting simplified page content...")
        try:
            html = await self._page.content()
            soup = BeautifulSoup(html, 'html.parser')
            interactive_elements = soup.find_all(['a', 'button', 'input', 'textarea', 'select', 'label'])
            element_summaries = []
            for element in interactive_elements:
                summary = f"<{element.name}"
                attrs_to_check = ['id', 'class', 'aria-label', 'placeholder', 'name', 'type', 'href']
                for attr in attrs_to_check:
                    if element.has_attr(attr):
                        value = element[attr]
                        if isinstance(value, list): value = " ".join(value)
                        summary += f' {attr}="{value[:100]}"'
                text = element.get_text(strip=True)
                summary += f">{text[:100]}</{element.name}>" if text else "/>"
                element_summaries.append(summary)
            return " ".join(element_summaries)
        except Exception as e:
            logger.error(f"Failed to get page content: {e}")
            return "Error: Could not retrieve page content."

    async def navigate(self, url: str):
        await self.connect()
        logger.info(f"[BROWSER] Navigating to: {url}")
        await self._page.goto(url)

    async def click(self, selector: str):
        await self.connect()
        logger.info(f"[BROWSER] Clicking on '{selector}'")
        await self._page.click(selector)
        
    async def type_text(self, selector: str, text: str):
        await self.connect()
        logger.info(f"[BROWSER] Typing '{text}' into '{selector}'")
        await self._page.fill(selector, text)
        
    async def press_key(self, selector: str, key: str):
        await self.connect()
        logger.info(f"[BROWSER] Pressing key '{key}' on '{selector}'")
        await self._page.press(selector, key)
        
    async def wait(self, duration_seconds: int):
        logger.info(f"Waiting for {duration_seconds} seconds...")
        await asyncio.sleep(duration_seconds)

    async def scroll(self, direction: str):
        await self.connect()
        logger.info(f"Scrolling page {direction}")
        if direction == "down":
            await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        elif direction == "up":
            await self._page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(2)
        
    # --- FIX: Restore the missing methods ---
    async def wait_for_element(self, selector: str, timeout: int = 15000):
        await self.connect()
        logger.info(f"[BROWSER] Waiting for element '{selector}'")
        await self._page.wait_for_selector(selector, timeout=timeout)

    async def extract_data(self, selector: str, fields: Dict[str, str], limit: int) -> List[Dict[str, Any]]:
        await self.connect()
        logger.info(f"Extracting data from '{selector}' (limit: {limit})")
        
        results = []
        elements = await self._page.query_selector_all(selector)
        
        for i, element in enumerate(elements):
            if i >= limit: break
            item_data = {}
            for field_name, sub_selector in fields.items():
                try:
                    sub_element = await element.query_selector(sub_selector)
                    if sub_element:
                        item_data[field_name] = await sub_element.inner_text()
                    else:
                        item_data[field_name] = None
                except Exception as e:
                    logger.warning(f"Could not extract field '{field_name}' using selector '{sub_selector}': {e}")
                    item_data[field_name] = None
            results.append(item_data)
        return results
    # --- END FIX ---