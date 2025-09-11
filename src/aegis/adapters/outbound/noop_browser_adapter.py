from typing import List, Dict, Any
from .browser_adapter import BrowserAdapter

class NoOpBrowserAdapter(BrowserAdapter):
    def navigate(self, url: str):
        print(f"--- NoOpBrowser: Navigating to {url}")

    def click(self, selector: str):
        print(f"--- NoOpBrowser: Clicking on element '{selector}'")

    def type_text(self, selector: str, text: str):
        print(f"--- NoOpBrowser: Typing '{text}' into element '{selector}'")

    def wait_for_element(self, selector: str):
        print(f"--- NoOpBrowser: Waiting for element '{selector}'")

    def extract_data(self, selector: str, fields: list, limit: int) -> list:
        print(f"--- NoOpBrowser: Extracting data from '{selector}'")
        # Return dummy data that matches the structure
        return [
            {"title": "Dummy Title 1", "team": "Dummy Team 1", "url": "/dummy1"},
            {"title": "Dummy Title 2", "team": "Dummy Team 2", "url": "/dummy2"},
        ]
