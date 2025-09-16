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
                tool_output_str = json.dumps(resp["tool_output"])
                gemini_parts.append({"function_response": {"name": resp["tool_name"], "response": {"content": tool_output_str}}})
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
                name="get_page_html",
                description="A debugging tool that gets the full inner HTML of a single element, specified by a CSS selector.",
                parameters={"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]},
            ),
            FunctionDeclaration(
                name="find_elements",
                description="Finds all elements matching a CSS selector and returns a list of their unique selectors.",
                parameters={"type": "object", "properties": {"selector": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["selector"]},
            ),
            FunctionDeclaration(
                name="process_posts_in_batches",
                description="For the MAIN feed. Takes a list of post selectors and extracts details from all of them.",
                parameters={"type": "object", "properties": {"post_selectors": {"type": "array", "items": {"type": "string"}}}, "required": ["post_selectors"]},
            ),
            FunctionDeclaration(
                name="process_activity_posts_in_batches",
                description="For a user's ACTIVITY page. Takes a list of post selectors and extracts details from all of them.",
                parameters={"type": "object", "properties": {"post_selectors": {"type": "array", "items": {"type": "string"}}}, "required": ["post_selectors"]},
            ),
            FunctionDeclaration(name="navigate", description="Navigates to a URL.", parameters={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}),
            FunctionDeclaration(name="scroll", description="Scrolls the page down.", parameters={"type": "object", "properties": {"direction": {"type": "string", "enum": ["down"]}}, "required": ["direction"]}),
            FunctionDeclaration(name="click", description="Clicks an element.", parameters={"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}),
            FunctionDeclaration(name="find_element", description="Finds a single element.", parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}),
            FunctionDeclaration(name="paste", description="Pastes text into an element.", parameters={"type": "object", "properties": {"selector": {"type": "string"}, "text": {"type": "string"}}, "required": ["selector", "text"]}),
            FunctionDeclaration(name="finish_task", description="Call when the goal is accomplished.", parameters={"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}),
            FunctionDeclaration(
                name="wait",
                description="Pauses execution for a specified number of seconds to allow content to load.",
                parameters={"type": "object", "properties": {"seconds": {"type": "integer"}}, "required": ["seconds"]},
            ),   
            FunctionDeclaration(
                name="wait_for_element",
                description="Waits for an element to appear in the DOM before proceeding.",
                parameters={"type": "object", "properties": {"selector": {"type": "string"}, "timeout": {"type": "integer"}}, "required": ["selector"]},
            ),         
        ]
        
        self.system_instruction = (
            "You are a web automation robot. Your only purpose is to execute the user's numbered plan. You must follow the rules absolutely:\n"
            "1. **Determine Next Step**: Identify the next numbered step from the user's plan that you have not yet executed.\n"
            "2. **Execute ONE Tool**: Call the single tool that completes that specific step. Use the correct tool for the job (e.g., `process_activity_posts_in_batches` for activity pages).\n"
            "3. **FINISH**: After completing the final step, call `finish_task`."
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