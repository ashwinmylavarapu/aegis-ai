import asyncio
from typing import Dict, Any
from loguru import logger
from fastmcp import Client

class BrowserMCPAdapter:
    def __init__(self, config: Dict[str, Any]):
        self.client = None
        self.is_connected = False  # Track connection state explicitly
        self.config = config.get("browser_mcp", {})

    async def connect(self):
        # We only connect if we haven't already.
        # The server is now assumed to be running, managed by the Chrome Extension.
        if not self.is_connected:
            mcp_url = self.config.get("url", "http://localhost:6279/mcp/")
            logger.info(f"Attempting to connect to pre-existing BrowserMCP server at: {mcp_url}")

            client_config = {
                "mcpServers": {
                    "browsermcp_server": {"url": mcp_url}
                }
            }
            self.client = Client(client_config)
            try:
                await self.client.__aenter__()
                self.is_connected = True  # Set state to connected only on success
                logger.success("Connected to BrowserMCP server.")
            except Exception as e:
                logger.error(f"Failed to connect to BrowserMCP server: {e}")
                # Re-raise the exception to signal failure to the orchestrator
                raise

    async def navigate(self, url: str):
        await self.connect()
        logger.info(f"[BROWSER] Navigating to: {url}")
        await self.client.call_tool("browsermcp_server_navigate", {"url": url})

    async def type_text(self, selector: str, text: str):
        await self.connect()
        logger.info(f"[BROWSER] Typing '{text}' into '{selector}'")
        await self.client.call_tool("browsermcp_server_type", {"element": selector, "text": text, "submit": False})

    async def click(self, selector: str):
        await self.connect()
        logger.info(f"[BROWSER] Clicking on '{selector}'")
        await self.client.call_tool("browsermcp_server_click", {"element": selector, "ref": ""})

    async def wait_for_element(self, selector: str):
        await self.connect()
        logger.info(f"[BROWSER] Waiting for element '{selector}'")
        await self.client.call_tool("browsermcp_server_wait", {"time": 2})

    async def extract_data(self, selector: str, fields: list, limit: int):
        await self.connect()
        logger.info(f"[BROWSER] Extracting data from '{selector}' (limit: {limit})")
        # This remains a mock until we can successfully connect and interact
        return [
            {"title": "Senior Python Developer", "team": "Platform", "url": "https://jobs.our-company.com/jobs/1"},
            {"title": "Python Developer", "team": "Data Science", "url": "https://jobs.our-company.com/jobs/2"},
            {"title": "Senior Python Engineer (Backend)", "team": "API", "url": "https://jobs.our-company.com/jobs/3"},
        ]

    async def close(self):
        if self.client and self.is_connected:
            logger.info("Closing BrowserMCP client connection...")
            await self.client.__aexit__(None, None, None)
            self.is_connected = False
            logger.info("BrowserMCP client connection closed.")

_browser_adapter_instance = None

def get_browser_adapter(config: Dict[str, Any]):
    global _browser_adapter_instance
    if _browser_adapter_instance is None:
        logger.debug("Creating new BrowserMCPAdapter instance")
        _browser_adapter_instance = BrowserMCPAdapter(config)
    return _browser_adapter_instance