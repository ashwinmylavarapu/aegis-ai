# src/aegis/adapters/outbound/google_genai_adapter.py
from typing import List, Dict, Any
import json
import google.generativeai as genai
from google.generativeai.types import content_types
from loguru import logger

from aegis.core.models import Message, ToolCall
from aegis.core.context_manager import ContextTrimmer
from .base import LLMAdapter

SYSTEM_INSTRUCTION = """
You are Aegis, a web automation agent. Your task is to execute the user's single-step instruction.
You must choose one and only one tool to accomplish the user's goal.
"""

class GoogleGenAIAdapter(LLMAdapter):
    def __init__(self, config: Dict[str, Any], tools: List[Dict[str, Any]] = None):
        llm_config = config.get("llm", {}).get("google_genai", {})
        api_key = llm_config.get("api_key")
        model_name = llm_config.get("model", "gemini-1.5-flash-latest")

        if not api_key:
            raise ValueError("API key for Google GenAI is missing from config.yaml")

        # --- DEBUGGING STEP ---
        # Log the beginning and end of the API key to verify it's being loaded correctly.
        # This is safe and does not expose the full key in logs.
        key_preview = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "key is too short to preview"
        logger.debug(f"Attempting to configure Google GenAI with API key preview: {key_preview}")
        # --- END DEBUGGING STEP ---


        genai.configure(api_key=api_key)
        
        if tools:
            logger.debug(f"Initializing Google GenAI model WITH tools: {json.dumps(tools, indent=2)}")
        else:
            logger.debug("Initializing Google GenAI model WITHOUT tools (text-generation only).")

        self.model = genai.GenerativeModel(
            model_name,
            tools=tools,
            system_instruction=SYSTEM_INSTRUCTION if tools else None,
        )
        self.trimmer = ContextTrimmer(config)
        logger.info(f"GoogleGenAIAdapter initialized with model: {model_name}")

    async def chat_completion(self, messages: List[Message]) -> Message:
        trimmed_messages = self.trimmer.trim(messages)
        history = self._format_messages_for_google(trimmed_messages)
        
        try:
            token_count = await self.model.count_tokens_async(history)
            logger.debug(
                "--- Preparing to Send Request to LLM ---\n"
                f"Original message count: {len(messages)}, Trimmed message count: {len(history)}.\n"
                f"Payload token count: {token_count.total_tokens}\n"
                f"Final conversation history being sent:\n{json.dumps(history, indent=2, default=str)}"
            )
        except Exception as e:
            logger.error(f"Fatal: Could not calculate token count before sending. Error: {e}")
            logger.debug(f"History that failed token count: {json.dumps(history, indent=2, default=str)}")
            raise

        chat = self.model.start_chat(history=history[:-1])
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