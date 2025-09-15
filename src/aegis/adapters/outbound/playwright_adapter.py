import asyncio
import platform
from typing import Dict, Any, List, Optional
import re

from loguru import logger
from playwright.async_api import async_playwright, Browser, Page, Playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from thefuzz import process

from .browser_adapter import BrowserAdapter

class PlaywrightAdapter(BrowserAdapter):
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get("browser", {}).get("playwright", {})
        self.cdp_endpoint = self.config.get("cdp_endpoint")
        if not self.cdp_endpoint:
            raise ValueError("Playwright config missing 'cdp_endpoint'")
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self.is_connected = False

    async def connect(self):
        if self.is_connected:
            return
        logger.info(f"Connecting to browser at CDP endpoint: {self.cdp_endpoint}")
        self._playwright = await async_playwright().start()
        try:
            self._browser = await self._playwright.chromium.connect_over_cdp(self.cdp_endpoint)
            if self._browser.contexts and self._browser.contexts[0].pages:
                self._page = self._browser.contexts[0].pages[0]
            else:
                context = await self._browser.new_context()
                self._page = await context.new_page()
            self.is_connected = True
            logger.success("Successfully connected to browser.")
        except Exception as e:
            await self.close()
            raise ConnectionError(f"Failed to connect to browser: {e}")

    async def close(self):
        if self._browser and self._browser.is_connected():
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._browser, self._page, self._playwright, self.is_connected = None, None, None, False
        logger.info("Playwright connection closed.")

    async def _get_interactive_elements(self) -> List[Dict[str, str]]:
        if not self._page:
            raise ConnectionError("Page is not initialized. Call connect() first.")
        
        html_content = await self._page.content()
        soup = BeautifulSoup(html_content, 'html.parser')
        
        elements = []
        interactive_tags = ['a', 'button', 'input', 'textarea', 'select', 'label']
        
        for tag in soup.find_all(interactive_tags):
            text = " ".join(tag.get_text(strip=True).split())
            description = text or tag.get('aria-label', '') or tag.get('placeholder', '') or tag.get('name', '')
            
            if description:
                escaped_text = text.replace('"', '\\"')
                selector = f'{tag.name}:has-text("{escaped_text}")'
                elements.append({"selector": selector, "description": description})
                
        return elements

    async def find_element(self, query: str) -> str:
        await self.connect()
        logger.info(f"[BROWSER] Finding element for query: '{query}'")
        try:
            elements = await self._get_interactive_elements()
            if not elements: return "Error: No interactive elements found."
            choices = {elem['description']: elem['selector'] for elem in elements}
            best_match = process.extractOne(query, choices.keys(), score_cutoff=80)
            if best_match:
                selector = choices[best_match[0]]
                logger.success(f"Found best match for '{query}': '{selector}' (Description: '{best_match[0]}')")
                return selector
            logger.warning(f"Could not find a suitable element for query: '{query}'")
            return "Error: Element not found."
        except Exception as e:
            logger.error(f"An error occurred during find_element: {e}")
            return f"Error: An exception occurred - {e}"

    async def navigate(self, url: str) -> str:
        await self.connect()
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        logger.info(f"[BROWSER] Navigating to {url}")
        await self._page.goto(url, wait_until="domcontentloaded")
        return f"Successfully navigated to {url}"

    async def type_text(self, selector: str, text: str) -> str:
        await self.connect()
        logger.info(f"[BROWSER] Typing '{text}' into '{selector}'")
        await self._page.fill(selector, text)
        return f"Successfully typed text into '{selector}'"

    async def click(self, selector: str) -> str:
        await self.connect()
        logger.info(f"[BROWSER] Clicking '{selector}'")
        await self._page.click(selector)
        return f"Successfully clicked '{selector}'"

    async def scroll(self, direction: str) -> str:
        await self.connect()
        logger.info(f"[BROWSER] Scrolling {direction}")
        if direction == "down":
            await self._page.evaluate("window.scrollBy(0, window.innerHeight)")
        return f"Successfully scrolled {direction}"

    async def get_page_content(self, clean: bool = True) -> str:
        await self.connect()
        logger.info("[BROWSER] Getting page content")
        html = await self._page.content()
        if not clean: return html
        soup = BeautifulSoup(html, 'html.parser')
        for script_or_style in soup(['script', 'style']):
            script_or_style.decompose()
        text = '\n'.join(chunk for chunk in (phrase.strip() for line in (line.strip() for line in soup.get_text().splitlines()) for phrase in line.split("  ")) if chunk)
        return text

    async def wait_for_element(self, selector: str, timeout: int = 10) -> str:
        await self.connect()
        logger.info(f"[BROWSER] Waiting for element '{selector}' for {timeout}s")
        try:
            await self._page.wait_for_selector(selector, timeout=timeout * 1000)
            logger.success(f"Element '{selector}' appeared.")
            return f"Element '{selector}' is present."
        except PlaywrightTimeoutError:
            logger.warning(f"Timed out waiting for element '{selector}'.")
            return f"Error: Timed out waiting for element '{selector}'."

    async def extract_data(self, selector: str, fields: Dict[str, str], limit: int = 0) -> List[Dict[str, str]]:
        await self.connect()
        logger.info(f"[BROWSER] Extracting data from '{selector}' with limit {limit}")
        
        container_elements = await self._page.query_selector_all(selector)
        limit = int(limit)
        if limit > 0:
            container_elements = container_elements[:limit]
            
        results = []
        for container in container_elements:
            item_data = {}
            for field_name, field_selector in fields.items():
                element = await container.query_selector(field_selector)
                item_data[field_name] = await element.inner_text() if element else None
            results.append(item_data)
        logger.success(f"Extracted {len(results)} items.")
        return results

    async def find_elements(self, selector: str, limit: int = 0) -> List[str]:
        await self.connect()
        logger.info(f"[BROWSER] Finding all elements matching '{selector}'")
        elements = await self._page.query_selector_all(selector)
        limit = int(limit)
        if limit > 0:
            elements = elements[:limit]
        
        unique_selectors = [f"{selector} >> nth={i}" for i in range(len(elements))]
        logger.success(f"Found {len(unique_selectors)} elements.")
        return unique_selectors

    # --- THIS IS THE FINAL FIX ---
    # Upgrading the selectors to be more specific and resilient to ambiguity.
    async def get_post_details(self, post_selector: str) -> Dict[str, str]:
        """A specialized tool to reliably extract author and text from a single LinkedIn post."""
        await self.connect()
        logger.info(f"[BROWSER] Getting details for post: '{post_selector}'")
        
        # A more specific selector for the post text that avoids translated versions.
        text_selector = "div.update-components-text.relative.update-components-update-v2__commentary"
        # The selector for the author's name remains reliable.
        author_selector = "span.update-components-actor__name > span[aria-hidden='true']"
        
        try:
            post_element = self._page.locator(post_selector)
            
            # Use .first to ensure we only ever get one element, preventing strict mode violations.
            author_element = post_element.locator(author_selector).first
            author_name = await author_element.inner_text(timeout=2000) if await author_element.count() > 0 else "Unknown"
            
            text_element = post_element.locator(text_selector).first
            post_text = await text_element.inner_text(timeout=2000) if await text_element.count() > 0 else ""
            
            logger.success(f"Extracted post by '{author_name}'")
            return {"author": author_name, "text": post_text.strip()}
        except Exception as e:
            logger.warning(f"Could not extract details for post '{post_selector}': {e}")
            return {"author": "Error", "text": str(e)}