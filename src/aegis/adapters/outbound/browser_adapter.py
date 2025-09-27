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
    
    @abstractmethod
    async def get_activity_post_details(self, post_selector: str) -> Dict[str, Any]:
        """Gets specific details from a single activity post."""
        pass
    
    @abstractmethod
    async def wait(self, seconds: int) -> str:
        pass
        
    @abstractmethod
    async def paste_image(self, selector: str, image_bytes: bytes) -> str:
        """Pastes an image from a byte string into a specified element."""
        pass

    @abstractmethod
    async def take_screenshot(self, path: str) -> str:
        """Takes a screenshot of the current page and saves it to a path."""
        pass

    @abstractmethod
    async def press_key(self, key_combination: str) -> str:
        """Presses a single key or a combination of keys."""
        pass