# src/aegis/adapters/outbound/base.py
from abc import ABC, abstractmethod
from typing import List, Any

# Assuming 'Message' is defined in your models, which is required by the new architecture
from aegis.core.models import Message


class OutboundAdapter(ABC):
    """
    Abstract base class for outbound adapters that are not LLMs
    (e.g., Browser, OmniParser).
    """
    pass


class LLMAdapter(ABC):
    """Abstract base class for Large Language Model adapters."""
    @abstractmethod
    async def chat_completion(self, messages: List[Message]) -> Message:
        """Sends a list of messages to the LLM and gets a response."""
        pass