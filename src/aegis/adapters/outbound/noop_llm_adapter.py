# src/aegis/adapters/outbound/noop_llm_adapter.py
from typing import List
from loguru import logger

from .base import LLMAdapter
from aegis.core.models import Message


class NoOpLLMAdapter(LLMAdapter):
    """
    A no-operation LLM adapter for testing and dry-runs.
    Returns a pre-defined message without calling an actual LLM.
    """
    async def chat_completion(self, messages: List[Message]) -> Message:
        logger.info("--- NoOpLLMAdapter: Returning dummy completion ---")
        return Message(
            role="assistant",
            content="This is a dummy response from the NoOpLLMAdapter. The task is considered complete."
        )