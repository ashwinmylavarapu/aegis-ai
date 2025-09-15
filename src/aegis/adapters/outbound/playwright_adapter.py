import asyncio
import platform
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
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self.is_connected = False

    async def connect(self):
        if self.is_connected: return
        logger.info(f"Connecting to browser at CDP endpoint: {self.cdp_endpoint}")
        self._playwright = await async_playwright().start()
        try:
            self._browser = await self._playwright.chromium.connect_over_cdp(self.cdp_endpoint)
            # Use the first available page, or create a new one.
            self._page = self._browser.contexts[0].pages[0] if self._browser.contexts and self._browser.contexts[0].pages else await (await self._browser.new_context()).new_page()
            self.is_connected = True
            logger.success("Successfully connected to browser.")
        except Exception as e:
            await self.close()
            raise e

    async def close(self):
        if self._browser and self._browser.is_connected():
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._browser, self._page, self._playwright, self.is_connected = None, None, None, False
        logger.info("Playwright connection closed.")

    async def get_page_content(self) -> str:
        await self.connect()
        logger.info("[BROWSER] Getting simplified page content for agent...")
        html = await self._page.content()
        soup = BeautifulSoup(html, 'html.parser')
        for script in soup(["script", "style"]):
            script.extract()
        
        element_summaries = []
        interactive_tags = soup.find_all(['a', 'button', 'input', 'textarea', 'select', 'label'])
        interactive_tags.extend(soup.find_all(contenteditable='true'))

        for tag in interactive_tags:
            summary = f"<{tag.name}"
            attrs = {k: v for k, v in tag.attrs.items() if k in ['id', 'class', 'aria-label', 'placeholder', 'name', 'type', 'href', 'contenteditable']}
            for k, v in attrs.items():
                summary += f' {k}="{" ".join(v) if isinstance(v, list) else v}"'
            text = tag.get_text(strip=True)
            summary += f">{text[:100]}</{tag.name}>" if text else "/>"
            element_summaries.append(summary)
        return " ".join(element_summaries)

    async def navigate(self, url: str):
        await self.connect()
        logger.info(f"[BROWSER] Navigating to: {url}")
        await self._page.goto(url, wait_until='domcontentloaded')

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
        else:
            await self._page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(2)

    async def paste(self, selector: str):
        await self.connect()
        logger.info(f"[BROWSER] Pasting clipboard content into '{selector}'")
        await self._page.focus(selector)
        modifier = "Meta" if platform.system() == "Darwin" else "Control"
        await self._page.keyboard.press(f"{modifier}+V")
        
    async def wait_for_element(self, selector: str, timeout: int = 15000):
        await self.connect()
        logger.info(f"[BROWSER] Waiting for element '{selector}' with timeout {timeout}ms")
        await self._page.wait_for_selector(selector, timeout=timeout)

    async def extract_data(self, selector: str, fields: Dict[str, str], limit: int) -> List[Dict[str, Any]]:
        await self.connect()
        logger.info(f"Extracting data from '{selector}' with limit {limit}")
        results = []
        elements = await self._page.query_selector_all(selector)
        for i, element in enumerate(elements):
            if i >= limit: break
            item_data = {}
            for field_name, sub_selector in fields.items():
                try:
                    sub_element = await element.query_selector(sub_selector)
                    item_data[field_name] = await sub_element.inner_text() if sub_element else None
                except Exception as e:
                    item_data[field_name] = f"Error extracting: {e}"
            results.append(item_data)
        return results