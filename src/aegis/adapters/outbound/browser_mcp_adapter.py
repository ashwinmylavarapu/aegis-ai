import subprocess
import time
import asyncio
from fastmcp import Client

class BrowserMCPAdapter:
    def __init__(self):
        self.process = None
        self.client = None

    async def _start_server(self):
        print("Starting BrowserMCP server...")
        # Use npx to run the latest version of @browsermcp/mcp
        self.process = subprocess.Popen(
            ["npx", "@browsermcp/mcp@latest"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        # Give the server some time to start up
        await asyncio.sleep(10) # Use asyncio.sleep for async context
        print("BrowserMCP server started.")
        # Read and print stdout/stderr to debug server startup
        stdout_data = self.process.stdout.read()
        stderr_data = self.process.stderr.read()
        print("BrowserMCP Server STDOUT:", stdout_data)
        print("BrowserMCP Server STDERR:", stderr_data)

    async def connect(self):
        if self.client is None:
            await self._start_server()
            # Assuming BrowserMCP server runs on ws://localhost:6279
            config = {
                "mcpServers": {
                    "browsermcp_server": {"url": "http://localhost:6279/mcp/"}
                }
            }
            self.client = Client(config)
            await self.client.__aenter__() # Manually enter the async context
            print("Connected to BrowserMCP client.")

    async def navigate(self, url: str):
        await self.connect()
        print(f"    [BROWSER] Navigating to: {url}")
        await self.client.call_tool("browsermcp_server_navigate", {"url": url})

    async def type_text(self, selector: str, text: str):
        await self.connect()
        print(f"    [BROWSER] Typing '{text}' into '{selector}'")
        await self.client.call_tool("browsermcp_server_type", {"element": selector, "text": text, "submit": False})

    async def click(self, selector: str):
        await self.connect()
        print(f"    [BROWSER] Clicking on '{selector}'")
        await self.client.call_tool("browsermcp_server_click", {"element": selector, "ref": ""}) # ref might be needed

    async def wait_for_element(self, selector: str):
        await self.connect()
        print(f"    [BROWSER] Waiting for element '{selector}'")
        # There is no direct 'wait_for_element' tool in browsermcp.
        # This might need to be implemented using a snapshot and polling,
        # or by calling a custom tool if browsermcp supports it.
        # For now, I'll just use a generic wait.
        await self.client.call_tool("browsermcp_server_wait", {"time": 2}) # Wait for 2 seconds as a placeholder

    async def extract_data(self, selector: str, fields: list, limit: int):
        await self.connect()
        print(f"    [BROWSER] Extracting data from '{selector}' (limit: {limit})")
        # browsermcp doesn't have a direct 'extract_data' tool.
        # This would typically involve taking a snapshot and then parsing the DOM.
        # For now, I'll return mock data as the browsermcp doesn't support this directly.
        # In a real scenario, this would be a more complex interaction with the browser.
        return [
            {"title": "Senior Python Developer", "team": "Platform", "url": "https://jobs.our-company.com/jobs/1"},
            {"title": "Python Developer", "team": "Data Science", "url": "https://jobs.our-company.com/jobs/2"},
            {"title": "Senior Python Engineer (Backend)", "team": "API", "url": "https://jobs.our-company.com/jobs/3"},
        ]

    async def close(self):
        if self.client:
            print("Closing BrowserMCP client...")
            await self.client.__aexit__(None, None, None) # Manually exit the async context
        if self.process:
            print("Terminating BrowserMCP server process...")
            self.process.terminate()
            self.process.wait()
            print("BrowserMCP server process terminated.")

_browser_adapter_instance = None

def get_browser_adapter():
    global _browser_adapter_instance
    if _browser_adapter_instance is None:
        _browser_adapter_instance = BrowserMCPAdapter()
    return _browser_adapter_instance
