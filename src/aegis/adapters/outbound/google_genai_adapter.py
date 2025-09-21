# src/aegis/adapters/outbound/google_genai_adapter.py
from typing import List, Dict, Any
import json
import google.generativeai as genai
from google.generativeai.types import content_types
from loguru import logger

from aegis.core.models import Message, ToolCall
from aegis.adapters.outbound.playwright_adapter import PlaywrightAdapter
from .base import LLMAdapter

SYSTEM_INSTRUCTION = """
You are Aegis, a web automation agent. Your task is to execute the user's single-step instruction.
You must choose one and only one tool to accomplish the user's goal.
"""

class GoogleGenAIAdapter(LLMAdapter):
    def __init__(self, config: Dict[str, Any]):
        llm_config = config.get("llm", {}).get("google_genai", {})
        api_key = llm_config.get("api_key")
        model_name = llm_config.get("model", "gemini-1.5-flash-latest")

        if not api_key:
            raise ValueError("API key for Google GenAI is missing from config.yaml")

        genai.configure(api_key=api_key)
        
        tools = PlaywrightAdapter.get_tools()
        logger.debug(f"--- Loading Tools into GoogleGenAIAdapter ---")
        logger.debug(f"Found {len(tools)} tools to load.")
        logger.debug(f"Tools JSON: {json.dumps(tools, indent=2)}")
        logger.debug("-----------------------------------------")

        self.model = genai.GenerativeModel(
            model_name,
            tools=tools,
            system_instruction=SYSTEM_INSTRUCTION,
        )
        logger.info(f"GoogleGenAIAdapter initialized with model: {model_name}")

    async def chat_completion(self, messages: List[Message]) -> Message:
        history = self._format_messages_for_google(messages)
        
        logger.debug(f"--- Sending New Request to LLM ---")
        logger.debug(f"Full conversation history being sent:\n{json.dumps(history, indent=2, default=str)}")
        
        # The history for the chat model should be all but the last message
        chat = self.model.start_chat(history=history[:-1])
        
        # The last message is the one we are sending
        response = await chat.send_message_async(history[-1]['parts'])

        logger.debug(f"Raw LLM response object:\n{response}")
        logger.debug("------------------------------------")

        return self._format_google_response_to_message(response)

    def _format_messages_for_google(self, messages: List[Message]) -> list:
        google_messages = []
        for msg in messages:
            role = "user" if msg.role in ["user", "system"] else "model"
            parts = []
            if msg.content:
                parts.append(msg.content)
            if msg.role == "tool" and msg.tool_responses:
                for tr in msg.tool_responses:
                    parts.append(content_types.to_part({"function_response": {"name": tr.tool_name, "response": {"content": tr.content}}}))
            if msg.role == "assistant" and msg.tool_calls:
                 for tc in msg.tool_calls:
                    parts.append(content_types.to_part({"function_call": {"name": tc.function_name, "args": tc.function_args}}))
            google_messages.append({"role": role, "parts": parts})
        return google_messages

    def _format_google_response_to_message(self, response) -> Message:
        try:
            if response.candidates and response.candidates[0].content.parts and response.candidates[0].content.parts[0].function_call:
                tool_calls = []
                for part in response.candidates[0].content.parts:
                    if fc := part.function_call:
                        tool_calls.append(ToolCall(id=fc.name, function_name=fc.name, function_args=dict(fc.args)))
                return Message(role="assistant", content=None, tool_calls=tool_calls)
            else:
                return Message(role="assistant", content=response.text)
        except (AttributeError, IndexError):
            logger.warning("Could not parse LLM response, falling back to text.")
            return Message(role="assistant", content=response.text if hasattr(response, 'text') else "")