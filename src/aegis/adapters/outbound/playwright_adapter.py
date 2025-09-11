import asyncio
from typing import Dict, Any, List, Optional
from loguru import logger
from playwright.async_api import async_playwright, Browser, Page, Playwright

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

    async def navigate(self, url: str):
        await self.connect()
        logger.info(f"[BROWSER] Navigating to: {url}")
        await self._page.goto(url)

    async def click(self, selector: str, wait_for_navigation: bool = False):
        await self.connect()
        logger.info(f"[BROWSER] Clicking on '{selector}'")
        if wait_for_navigation:
            async with self._page.expect_navigation():
                await self._page.click(selector)
        else:
            await self._page.click(selector)
        
    async def type_text(self, selector: str, text: str):
        await self.connect()
        logger.info(f"[BROWSER] Typing '{text}' into '{selector}'")
        await self._page.fill(selector, text)
        
    async def press_key(self, selector: str, key: str, wait_for_navigation: bool = False):
        await self.connect()
        logger.info(f"[BROWSER] Pressing key '{key}' on '{selector}'")
        if wait_for_navigation:
            async with self._page.expect_navigation():
                await self._page.press(selector, key)
        else:
            await self._page.press(selector, key)
        
    async def wait_for_element(self, selector: str, timeout: Optional[int] = None):
        await self.connect()
        # Use the provided timeout, or fall back to a long default of 60 seconds
        final_timeout = timeout if timeout is not None else 60000 
        logger.info(f"[BROWSER] Waiting for element '{selector}' for up to {final_timeout}ms")
        await self._page.wait_for_selector(selector, timeout=final_timeout)

    async def search_jobs(self, query: str):
        await self.connect()
        logger.info(f"[ACTION] Performing job search for: '{query}'")
        search_input_selectors = ["input[aria-label='Search by title, skill, or company']", ".jobs-search-box__text-input", "input[id*='job-search-bar-keywords']"]
        for i, selector in enumerate(search_input_selectors):
            try:
                logger.debug(f"Attempting to type using selector {i+1}: {selector}")
                await self.type_text(selector, query)
                await self.press_key(selector, "Enter")
                break
            except Exception:
                if i == len(search_input_selectors) - 1: raise
        
        results_selectors = [".jobs-search__results-list", ".scaffold-layout__list-container", "main.scaffold-layout__main"]
        combined_selector = ", ".join(results_selectors)
        logger.info(f"Waiting for search results to load with combined selector: {combined_selector}")
        await self.wait_for_element(combined_selector)
        logger.success("Job search and wait for results completed successfully.")

    async def extract_data(self, selector: str, fields: List[str], limit: int) -> List[Dict[str, Any]]:
        await self.connect()
        logger.info(f"Extracting data from '{selector}' (limit: {limit})")
        field_to_selector_map = {"title": "h3.base-search-card__title", "company": "h4.base-search-card__subtitle", "location": ".job-search-card__location", "url": "a.base-card__full-link"}
        results, elements = [], await self._page.query_selector_all(selector)
        for i, element in enumerate(elements):
            if i >= limit: break
            item_data = {}
            for field in fields:
                try:
                    css_selector = field_to_selector_map.get(field)
                    if not css_selector: item_data[field] = None; continue
                    sub_element = await element.query_selector(css_selector)
                    if field == "url":
                        item_data[field] = await sub_element.get_attribute('href') if sub_element else None
                    else:
                        item_data[field] = await sub_element.inner_text() if sub_element else None
                except Exception:
                    item_data[field] = None
            results.append(item_data)
        return results