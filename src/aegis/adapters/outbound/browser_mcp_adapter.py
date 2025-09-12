import asyncio
from typing import Dict, Any, List
from loguru import logger
from fastmcp.client import Client

from .browser_adapter import BrowserAdapter

class BrowserMCPAdapter(BrowserAdapter):
    """An adapter to connect to a running BrowserMCP WebSocket server."""
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get("browser_mcp", {})
        mcp_url = self.config.get("url")
        if not mcp_url:
            raise ValueError("BrowserMCP config missing 'url' in config.yaml")

        client_config = {"mcpServers": {"browsermcp_server": {"url": mcp_url}}}
        self.client = Client(client_config)
        self.is_connected = False
        logger.info(f"BrowserMCPAdapter initialized for URL: {mcp_url}")

    async def connect(self):
        if self.is_connected:
            return
        logger.info(f"Connecting to BrowserMCP server at {self.config.get('url')}")
        await self.client.__aenter__()
        self.is_connected = True
        logger.success("Connected to BrowserMCP server.")

    async def close(self):
        if self.is_connected:
            logger.info("Closing connection to BrowserMCP server.")
            await self.client.__aexit__(None, None, None)
            self.is_connected = False
    
    async def call_mcp_tool(self, tool_name: str, **kwargs):
        """Helper to call a tool on the MCP server."""
        await self.connect()
        # The AI agent generates the simple tool name, we add the required prefix.
        full_tool_name = f"browsermcp_server_{tool_name}"
        logger.info(f"[BROWSER] Calling tool '{full_tool_name}' with args: {kwargs}")
        return await self.client.call_tool(full_tool_name, kwargs)

    async def navigate(self, url: str):
        return await self.call_mcp_tool("navigate", url=url)

    async def click(self, selector: str):
        return await self.call_mcp_tool("click", element=selector)

    async def type_text(self, selector: str, text: str):
        return await self.call_mcp_tool("type", element=selector, text=text)

    async def press_key(self, selector: str, key: str):
        # The selector is often optional for a general key press
        return await self.call_mcp_tool("press_key", key=key)

    async def get_page_content(self) -> str:
        return await self.call_mcp_tool("snapshot")

    async def scroll(self, direction: str):
        key = "PageDown" if direction == "down" else "PageUp"
        return await self.call_mcp_tool("press_key", key=key)
        
    async def wait(self, duration_seconds: int):
        logger.info(f"Client-side wait for {duration_seconds} seconds...")
        await asyncio.sleep(duration_seconds)

    async def wait_for_element(self, selector: str, timeout: int = 15000):
        # BrowserMCP does not have a native wait_for_element tool.
        # This is a client-side placeholder. The agent should use 'wait' for delays.
        logger.warning("BrowserMCPAdapter does not have a native 'wait_for_element' tool. Performing a short client-side wait.")
        await asyncio.sleep(2) # Short pause
        return

    async def extract_data(self, selector: str, fields: Dict[str, str], limit: int) -> List[Dict[str, Any]]:
        # This is a complex action that the "Look, Think, Act" agent handles by
        # first using get_page_content and then reasoning about the result.
        logger.warning("BrowserMCPAdapter relies on the agent to perform extraction after 'get_page_content'. This tool does not perform an action.")
        return []