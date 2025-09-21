# src/aegis/adapters/outbound/google_genai_adapter.py
from typing import List, Dict, Any
import google.generativeai as genai
from google.generativeai.types import content_types
from loguru import logger

from aegis.core.models import Message, ToolCall
from aegis.adapters.outbound.playwright_adapter import PlaywrightAdapter
from .base import LLMAdapter

# Final, corrected system prompt for accurate visual reasoning
SYSTEM_INSTRUCTION = """
You are Aegis, a web automation agent. Your task is to execute the user's single-step instruction.

**Action Cycle:**
1.  **Analyze Goal & Visuals**: The user will provide a goal and a list of visible UI elements (`element_id`, description, text, coordinates).
2.  **Select ONE Tool**: Based on the goal and visuals, choose the single best tool.
    * **To TYPE**: Find the correct input field from the visual list. Call `type_text_coords` with its coordinates and the specified text.
    * **To PRESS a key**: Call the `press_key` tool with the key name (e.g., 'Enter'). This requires no coordinates.
    * **To CLICK**: Find the button or link in the visual list. Call `click_coords` with its coordinates.
    * **To NAVIGATE**: Use the `Maps` tool with the target URL.
3.  **EXECUTE**: You must call one tool. Do not ask questions or give explanations.
"""

class GoogleGenAIAdapter(LLMAdapter):
    def __init__(self, config: Dict[str, Any]):
        llm_config = config.get("llm", {}).get("google_genai", {})
        api_key = llm_config.get("api_key")
        model_name = llm_config.get("model", "gemini-1.5-flash-latest")

        if not api_key:
            raise ValueError("API key for Google GenAI is missing from config.yaml")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name,
            tools=PlaywrightAdapter.get_tools(),
            system_instruction=SYSTEM_INSTRUCTION,
        )
        logger.info(f"GoogleGenAIAdapter initialized with model: {model_name}")

    async def chat_completion(self, messages: List[Message]) -> Message:
        history = self._format_messages_for_google(messages)
        current_message = history.pop() if history else ""

        chat = self.model.start_chat(history=history)
        response = await chat.send_message_async(current_message)

        return self._format_google_response_to_message(response)

    def _format_messages_for_google(self, messages: List[Message]) -> list:
        google_messages = []
        for msg in messages:
            role = "user" if msg.role in ["user", "system"] else "model"
            parts = []
            if msg.content:
                parts.append(msg.content)

            # --- THIS IS THE FIX ---
            # Correctly format tool responses for the Google GenAI library
            if msg.role == "tool" and msg.tool_responses:
                for tr in msg.tool_responses:
                    parts.append(content_types.to_part(
                        {"function_response": {"name": tr.tool_name, "response": {"content": tr.content}}}
                    ))
            
            # Append tool calls if they exist on an assistant message
            if msg.role == "assistant" and msg.tool_calls:
                 for tc in msg.tool_calls:
                    parts.append(content_types.to_part(
                        {"function_call": {"name": tc.function_name, "args": tc.function_args}}
                    ))

            google_messages.append({"role": role, "parts": parts})
        return google_messages

    def _format_google_response_to_message(self, response) -> Message:
        try:
            # Check for tool calls in the response
            if response.candidates and response.candidates[0].content.parts and response.candidates[0].content.parts[0].function_call:
                tool_calls = []
                for part in response.candidates[0].content.parts:
                    if fc := part.function_call:
                        tool_calls.append(
                            ToolCall(
                                id=fc.name,
                                function_name=fc.name,
                                function_args=dict(fc.args),
                            )
                        )
                return Message(role="assistant", content=None, tool_calls=tool_calls)
            else:
                # Fallback to text response if no tool call
                return Message(role="assistant", content=response.text)
        except (AttributeError, IndexError):
            logger.warning("Could not parse LLM response, falling back to text.")
            return Message(role="assistant", content=response.text if hasattr(response, 'text') else "")