# src/aegis/core/context_manager.py
from typing import Dict, List
from loguru import logger

from .models import AegisContext, Playbook, Message, ToolResponse

class ContextManager:
    """
    Manages the runtime context for playbook executions.
    """
    _contexts: Dict[str, AegisContext] = {}

    def create_context(self, playbook: Playbook) -> AegisContext:
        context_key = playbook.name
        logger.info(f"Creating new context for playbook: '{context_key}'")
        initial_message = Message(role="system", content=playbook.persona)
        aegis_context = AegisContext(
            playbook=playbook,
            messages=[initial_message]
        )
        self._contexts[context_key] = aegis_context
        return aegis_context

    # ... (get_context and clear_context methods remain the same) ...
    def get_context(self, context_key: str) -> AegisContext:
        if context_key not in self._contexts:
            raise ValueError(f"Context for key '{context_key}' not found.")
        return self._contexts[context_key]

    def clear_context(self, context_key: str):
        if context_key in self._contexts:
            del self._contexts[context_key]
            logger.info(f"Context for key '{context_key}' cleared.")


class ContextTrimmer:
    """Handles the logic for trimming the conversation history."""

    def __init__(self, config: Dict):
        ctx_config = config.get("context_management", {})
        self.max_history_items = ctx_config.get("max_history_items", 10)
        self.max_tool_output_tokens = ctx_config.get("max_tool_output_tokens", 2000)
        logger.info(
            "ContextTrimmer initialized. "
            f"Max history items: {self.max_history_items}, "
            f"Max tool output tokens: {self.max_tool_output_tokens}"
        )

    def trim(self, messages: List[Message]) -> List[Message]:
        """Trims messages to fit within the configured limits."""
        
        trimmed_messages = self._trim_tool_outputs(messages)

        # --- THIS IS THE FIX ---
        # Enforce a hard limit on the number of messages.
        if len(trimmed_messages) <= self.max_history_items:
            return trimmed_messages

        # Always keep the first message (system persona)
        system_message = [trimmed_messages[0]]
        
        # Keep the most recent N-1 messages
        num_recent_to_keep = self.max_history_items - 1
        recent_messages = trimmed_messages[-num_recent_to_keep:] if num_recent_to_keep > 0 else []
        
        final_messages = system_message + recent_messages
        
        logger.debug(
            f"Context trimmed: Original message count: {len(messages)}, "
            f"Trimmed message count: {len(final_messages)}"
        )
        return final_messages

    def _trim_tool_outputs(self, messages: List[Message]) -> List[Message]:
        """Truncates the content of tool responses if they are too long."""
        for msg in messages:
            if msg.role == "tool" and msg.tool_responses:
                for response in msg.tool_responses:
                    if len(response.content) > self.max_tool_output_tokens:
                        original_len = len(response.content)
                        response.content = (
                            response.content[:self.max_tool_output_tokens]
                            + "\n... [Output truncated]"
                        )
                        logger.warning(
                            f"Truncated tool output for '{response.tool_name}'. "
                            f"Original length: {original_len}, "
                            f"New length: {len(response.content)}"
                        )
        return messages