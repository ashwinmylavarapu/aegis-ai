import logging
from typing import List, Dict, Any

# Get a logger instance for this module
logger = logging.getLogger(__name__)

class ContextManager:
    """
    Manages the agent's history to prevent exceeding LLM context limits.
    This is achieved through two strategies:
    1. Truncating the content of large tool outputs.
    2. Limiting the total number of turns (messages) kept in history.
    """

    def __init__(self, max_history_items: int = 10, max_tool_output_tokens: int = 2000):
        """
        Initializes the context manager with configurable limits. These values
        should ideally be loaded from the main application config.

        Args:
            max_history_items: The maximum number of messages to keep in the history.
            max_tool_output_tokens: The maximum number of tokens for a single tool output.
                                     Outputs exceeding this will be truncated.
        """
        self.max_history_items = max_history_items
        self.max_tool_output_tokens = max_tool_output_tokens
        logger.info(f"ContextManager initialized with max_history_items={max_history_items}, max_tool_output_tokens={max_tool_output_tokens}")

    def _truncate_content(self, content: str) -> str:
        """
        Truncates a string if it exceeds the configured token limit.

        Note: This uses a simple character-based approximation where 1 token ~ 4 chars.
        For production-grade accuracy, a proper tokenizer library (e.g., tiktoken)
        should be used, but this approach is dependency-free and effective.
        """
        # Calculate the approximate maximum number of characters
        max_chars = self.max_tool_output_tokens * 4
        
        if len(content) > max_chars:
            truncated_content = content[:max_chars]
            # Create a clear warning message to be appended to the content
            warning = f"... [Output truncated to approximately {self.max_tool_output_tokens} tokens]"
            logger.warning(f"A tool output was too long ({len(content)} chars) and has been truncated.")
            return truncated_content + "\n\n" + warning
        return content

    def add_tool_result(self, history: List[Dict[str, Any]], tool_name: str, tool_output: Any) -> List[Dict[str, Any]]:
        """
        Adds a tool result to the history, applying content truncation if necessary.
        This should be called immediately after a tool is executed.
        """
        # Ensure the tool_output is in string format before processing
        if isinstance(tool_output, str):
            content = self._truncate_content(tool_output)
        else:
            # For non-string outputs (e.g., dicts, lists), convert them to a string
            # and then truncate. This can be improved with more sophisticated serialization.
            content = self._truncate_content(str(tool_output))

        tool_turn = {"type": "tool", "name": tool_name, "content": content}
        history.append(tool_turn)
        return history

    def manage(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Manages the overall history length by keeping only the most relevant messages.
        This should be called just before sending the history to the LLM.

        The strategy is to always keep the first message (the original prompt/goal)
        and the N most recent messages, where N is based on max_history_items.
        """
        if len(history) > self.max_history_items:
            logger.info(f"History length ({len(history)}) exceeds max ({self.max_history_items}). Truncating history.")
            # Keep the first message and the last (max_history_items - 1) messages
            return [history[0]] + history[-(self.max_history_items - 1):]
        return history