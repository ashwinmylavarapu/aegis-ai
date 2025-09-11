from abc import ABC, abstractmethod
from typing import Dict, Any

class BrowserAdapter(ABC):
    @abstractmethod
    def navigate(self, url: str):
        pass

    @abstractmethod
    def click(self, selector: str):
        pass

    @abstractmethod
    def type_text(self, selector: str, text: str):
        pass

    @abstractmethod
    def wait_for_element(self, selector: str):
        pass

    @abstractmethod
    def extract_data(self, selector: str, fields: list, limit: int) -> list:
        pass
