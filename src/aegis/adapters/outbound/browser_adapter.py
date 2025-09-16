from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BrowserAdapter(ABC):

    @abstractmethod
    async def navigate(self, url: str) -> str:
        pass

    @abstractmethod
    async def get_page_content(self, clean: bool = True) -> str:
        pass

    @abstractmethod
    async def type_text(self, selector: str, text: str) -> str:
        pass

    @abstractmethod
    async def paste(self, selector: str, text: str) -> str:
        pass

    @abstractmethod
    async def click(self, selector: str) -> str:
        pass

    @abstractmethod
    async def scroll(self, direction: str) -> str:
        pass

    @abstractmethod
    async def wait_for_element(self, selector: str, timeout: int) -> str:
        pass

    @abstractmethod
    async def extract_data(self, selector: str, fields: Dict[str, str], limit: int) -> List[Dict[str, Any]]:
        pass
    
    # --- THIS IS THE FIX (Part 1) ---
    # Add the new 'wait' method to the contract.
    @abstractmethod
    async def wait(self, seconds: int) -> str:
        pass