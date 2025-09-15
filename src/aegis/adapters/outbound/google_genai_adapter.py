import json
from typing import Dict, Any, List

from loguru import logger
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold, FunctionDeclaration, Tool
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import LLMAdapter

def convert_history_to_gemini(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    gemini_history = []
    for turn in history:
        if turn["type"] == "human":
            gemini_history.append({"role": "user", "parts": [{"text": turn["content"]}]})
        elif turn["type"] == "ai":
            tool_calls = turn["content"]
            gemini_parts = []
            for call in tool_calls:
                gemini_parts.append({"function_call": {"name": call["tool_name"], "args": call["tool_args"]}})
            gemini_history.append({"role": "model", "parts": gemini_parts})
        elif turn["type"] == "tool":
            tool_responses = turn["content"]
            gemini_parts = []
            for resp in tool_responses:
                gemini_parts.append({"function_response": {"name": resp["tool_name"], "response": {"content": resp["tool_output"]}}})
            gemini_history.append({"role": "tool", "parts": gemini_parts})
    return gemini_history

class GoogleGenAIAdapter(LLMAdapter):
    def __init__(self, config: Dict[str, Any]):
        llm_config = config.get("llm", {}).get("google_genai", {})
        api_key = llm_config.get("api_key")
        model_name = llm_config.get("model", "gemini-1.5-flash")

        if not api_key:
            raise ValueError("Google GenAI API key is missing from the config.")
        
        genai.configure(api_key=api_key)
        
        tool_declarations = [
            FunctionDeclaration(
                name="find_element",
                description="Finds the CSS selector for a single element on the page based on a natural language description. Use this for single interactions like clicking.",
                parameters={"type": "object", "properties": {"query": {"type": "string", "description": "A simple description of the element, e.g., 'the search bar'."}}, "required": ["query"]},
            ),
            FunctionDeclaration(
                name="type_text",
                description="Types text into an element identified by its CSS selector.",
                parameters={"type": "object", "properties": {"selector": {"type": "string"}, "text": {"type": "string"}}, "required": ["selector", "text"]},
            ),
            FunctionDeclaration(
                name="click",
                description="Clicks an element identified by its CSS selector.",
                parameters={"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]},
            ),
            FunctionDeclaration(
                name="scroll",
                description="Scrolls the page down to load more content.",
                parameters={"type": "object", "properties": {"direction": {"type": "string", "enum": ["down"]}}, "required": ["direction"]},
            ),
            FunctionDeclaration(
                name="navigate",
                description="Navigates the browser to a specific URL.",
                parameters={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
            ),
            FunctionDeclaration(
                name="wait_for_element",
                description="Waits for a specific element to appear on the page before proceeding. Useful for dynamic content.",
                parameters={"type": "object", "properties": {"selector": {"type": "string"}, "timeout": {"type": "integer", "description": "How many seconds to wait."}}, "required": ["selector"]},
            ),
            FunctionDeclaration(
                name="extract_data",
                description="Extracts a list of structured data from the page, like post details or search results.",
                parameters={
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string", "description": "The CSS selector for the repeating container element (e.g., a list item)."},
                        "fields": {"type": "object", "description": "A dictionary where keys are field names and values are CSS selectors relative to the container."},
                        "limit": {"type": "integer", "description": "The maximum number of items to extract."}
                    },
                    "required": ["selector", "fields"]
                },
            ),
            FunctionDeclaration(
                name="linkedin_login",
                description="Logs the user into LinkedIn using credentials from environment variables.",
            ),
            FunctionDeclaration(
                name="finish_task",
                description="Call this function when the high-level goal is fully accomplished, either successfully or because the requested information could not be found.",
                parameters={"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]},
            ),
        ]
        
        self.system_instruction = (
            "You are a web automation robot. Your only purpose is to execute a numbered list of instructions provided by the user. You must follow these rules absolutely:\n"
            "1.  **Examine History**: Look at the numbered plan from the user and the list of tools you have already executed.\n"
            "2.  **Determine Next Step**: Identify the single next numbered step from the user's plan that you have not yet executed.\n"
            "3.  **Execute ONE Tool for that Step**: Call the single tool that completes that specific step. For example, if the next step is `3c. Scroll down 2 times`, your ONLY valid action is to call the `scroll` tool. If the next step is `4a. Find the button...`, your ONLY valid action is to call `find_element`.\n"
            "4.  **DO NOT DEVIATE**: Do not repeat steps. Do not skip steps. Do not do anything other than the very next step in the plan.\n"
            "5.  **FINISH**: After you execute the tool for the final numbered step, your next and only action MUST be to call `finish_task`."
        )

        self.model = genai.GenerativeModel(model_name, tools=tool_declarations, system_instruction=self.system_instruction)
        logger.info(f"GoogleGenAIAdapter initialized for model: {model_name}")

    @retry(wait=wait_exponential(multiplier=2, min=5, max=60), stop=stop_after_attempt(3))
    async def generate_plan(self, history: List[Dict[str, Any]] = []) -> List[Dict[str, Any]]:
        logger.info(f"Generating plan based on conversation history.")
        gemini_history = convert_history_to_gemini(history)
        
        try:
            response = await self.model.generate_content_async(
                contents=gemini_history,
                generation_config={"temperature": 0.0},
                safety_settings={
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }
            )
            
            tool_calls = [{"tool_name": part.function_call.name, "tool_args": {k: v for k, v in part.function_call.args.items()}} for part in response.candidates[0].content.parts if part.function_call]
            
            if not tool_calls:
                logger.warning("LLM did not return any tool calls. Returning empty plan.")
                return []
                
            logger.success(f"Generated plan with {len(tool_calls)} tool call(s).")
            return tool_calls

        except Exception as e:
            logger.error(f"Error generating plan from Google GenAI: {e}")
            raise