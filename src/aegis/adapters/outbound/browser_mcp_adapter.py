"""
Adapter for interacting with the BrowserMCP server.
"""
from typing import List, Dict, Any

class BrowserMCPAdapter:
    """Placeholder for the real BrowserMCP adapter."""
    def navigate(self, url: str):
        print(f"--- Mock Browser: Navigating to {url}")

    def type_text(self, selector: str, text: str):
        print(f"--- Mock Browser: Typing '{text}' into '{selector}'")

    def click(self, selector: str):
        print(f"--- Mock Browser: Clicking '{selector}'")

    def wait_for_element(self, selector: str):
        print(f"--- Mock Browser: Waiting for '{selector}'")

    def extract_data(self, selector: str, fields: List[str], limit: int) -> List[Dict[str, Any]]:
        print(f"--- Mock Browser: Extracting data from '{selector}'")
        # Return mock data
        return [
            {"title": "Senior Python Developer", "team": "Platform", "url": "/1"},
            {"title": "Backend Engineer", "team": "API", "url": "/2"},
            {"title": "Data Scientist", "team": "Analytics", "url": "/3"},
        ]

def get_browser_adapter():
    """Returns a singleton instance of the Browser adapter."""
    return BrowserMCPAdapter()
