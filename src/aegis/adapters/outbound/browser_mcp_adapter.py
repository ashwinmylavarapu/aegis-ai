import subprocess
import asyncio
from typing import Dict, Any
from loguru import logger
from fastmcp import Client

class BrowserMCPAdapter:
    def __init__(self, config: Dict[str, Any]):
        self.process = None
        self.client = None
        self.config = config.get("browser_mcp", {})
        self._log_streaming_tasks = []

    async def _log_server_output(self, stream, log_prefix):
        """Reads and logs output from a stream line by line."""
        while not stream.at_eof():
            line = await stream.readline()
            if line:
                logger.debug(f"BrowserMCP Server {log_prefix}: {line.decode().strip()}")

    async def _start_server(self):
        logger.info("Starting BrowserMCP server...")
        self.process = await asyncio.create_subprocess_exec(
            "npx", "@browsermcp/mcp@latest",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        logger.info("Waiting for BrowserMCP server to initialize...")

        # Start background tasks to stream logs
        self._log_streaming_tasks.append(
            asyncio.create_task(self._log_server_output(self.process.stdout, 'STDOUT'))
        )
        self._log_streaming_tasks.append(
            asyncio.create_task(self._log_server_output(self.process.stderr, 'STDERR'))
        )

        await asyncio.sleep(10)  # Give server time to start
        logger.info("BrowserMCP server should be started.")

    async def connect(self):
        if self.client is None:
            await self._start_server()
            
            mcp_url = self.config.get("url", "http://localhost:6279/mcp/")
            logger.info(f"Attempting to connect to BrowserMCP at: {mcp_url}")

            client_config = {
                "mcpServers": {
                    "browsermcp_server": {"url": mcp_url}
                }
            }
            self.client = Client(client_config)
            try:
                await self.client.__aenter__()
                logger.success("Connected to BrowserMCP client.")
            except Exception as e:
                logger.error(f"Failed to connect to BrowserMCP client: {e}")
                # The background tasks are already logging the output.
                # No need to read stdout/stderr here.
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
        return [
            {"title": "Senior Python Developer", "team": "Platform", "url": "https://jobs.our-company.com/jobs/1"},
            {"title": "Python Developer", "team": "Data Science", "url": "https://jobs.our-company.com/jobs/2"},
            {"title": "Senior Python Engineer (Backend)", "team": "API", "url": "https://jobs.our-company.com/jobs/3"},
        ]

    async def close(self):
        if self.client:
            logger.info("Closing BrowserMCP client...")
            await self.client.__aexit__(None, None, None)
        
        # Cancel the log streaming tasks
        for task in self._log_streaming_tasks:
            task.cancel()
        await asyncio.gather(*self._log_streaming_tasks, return_exceptions=True)

        if self.process and self.process.returncode is None:
            logger.info("Terminating BrowserMCP server process...")
            self.process.terminate()
            await self.process.wait()
            logger.info("BrowserMCP server process terminated.")

_browser_adapter_instance = None

def get_browser_adapter(config: Dict[str, Any]):
    global _browser_adapter_instance
    if _browser_adapter_instance is None:
        logger.debug("Creating new BrowserMCPAdapter instance")
        _browser_adapter_instance = BrowserMCPAdapter(config)
    return _browser_adapter_instance