import json
from typing import Dict, Any, List
from loguru import logger
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold, FunctionDeclaration, Tool
from tenacity import retry, stop_after_attempt, wait_exponential
from .base import LLMAdapter

def convert_history_to_gemini(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    gemini_history = []
    for message in history:
        role = message["role"]
        if role == "assistant":
            parts = []
            for tc in message.get("tool_calls", []):
                func = tc.get("function", {})
                parts.append({'function_call': {"name": func.get("name"), "args": json.loads(func.get("arguments", '{}'))}})
            if parts: gemini_history.append({'role': 'model', 'parts': parts})
        elif role == "tool":
            gemini_history.append({'role': 'function', 'parts': [{'function_response': {'name': message.get('name'), 'response': {'content': message.get('content')}}}]})
    return gemini_history

class GoogleGenAIAdapter(LLMAdapter):
    def __init__(self, config: Dict[str, Any]):
        llm_config = config.get("llm", {}).get("google_genai_studio", {})
        api_key, model_name = llm_config.get("api_key"), llm_config.get("model", "gemini-pro")
        if not api_key: raise ValueError("Google GenAI config missing 'api_key'")
        genai.configure(api_key=api_key)
        
        tool_declarations = [
            FunctionDeclaration(name="get_page_content", description="Gets a simplified summary of the page's interactive elements."),
            FunctionDeclaration(name="navigate", description="Navigates to a URL.", parameters={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}),
            FunctionDeclaration(name="type_text", description="Types text into an element.", parameters={"type": "object", "properties": {"selector": {"type": "string"}, "text": {"type": "string"}}, "required": ["selector", "text"]}),
            FunctionDeclaration(name="click", description="Clicks an element.", parameters={"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}),
            FunctionDeclaration(name="press_key", description="Presses a key on an element.", parameters={"type": "object", "properties": {"selector": {"type": "string"},"key": {"type": "string"}}, "required": ["selector", "key"]}),
            FunctionDeclaration(name="wait", description="Pauses for a number of seconds.", parameters={"type": "object", "properties": {"duration_seconds": {"type": "integer"}}, "required": ["duration_seconds"]}),
            FunctionDeclaration(name="scroll", description="Scrolls the page.", parameters={"type": "object", "properties": {"direction": {"type": "string", "enum": ["up", "down"]}}, "required": ["direction"]}),
            FunctionDeclaration(name="paste", description="Pastes content from the clipboard into a focused element.", parameters={"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}),
            FunctionDeclaration(name="extract_data", description="Extracts data from a list of elements.", parameters={"type": "object", "properties": {"selector": {"type": "string"}, "limit": {"type": "integer"}, "fields": {"type": "object", "description": "A dictionary where keys are field names and values are CSS selectors."}}}),
            FunctionDeclaration(name="finish_task", description="Call when the goal is accomplished.", parameters={"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}),
        ]
        
        self.system_instruction = (
            "You are an expert AI web automation agent. You operate in a 'Look, Think, Act' cycle. "
            "1. **Look**: Always use `get_page_content` to understand the page. "
            "2. **Think**: Based on the content and goal, decide the next action and construct a precise CSS selector. "
            "3. **Act**: Execute the tool. Use `paste` to paste content from the clipboard. "
            "4. Repeat. If an action fails, use `get_page_content` again to re-evaluate. When the goal is complete, use `finish_task`."
        )

        self.model = genai.GenerativeModel(model_name, tools=tool_declarations, system_instruction=self.system_instruction)
        logger.info(f"GoogleGenAIAdapter initialized for model: {model_name}")

    @retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(3), reraise=True)
    async def generate_plan(self, goal: str, history: List[Dict[str, Any]] = []) -> List[Dict[str, Any]]:
        full_conversation = [{"role": "user", "parts": [{"text": goal}]}]
        full_conversation.extend(convert_history_to_gemini(history))
        try:
            safety_settings = {cat: HarmBlockThreshold.BLOCK_NONE for cat in HarmCategory if cat != HarmCategory.HARM_CATEGORY_UNSPECIFIED}
            response = await self.model.generate_content_async(full_conversation, safety_settings=safety_settings)
            response_part = response.candidates[0].content.parts[0]
            
            steps = []
            if hasattr(response_part, 'function_call') and response_part.function_call:
                fc = response_part.function_call
                args = {key: value for key, value in fc.args.items()}
                if 'fields' in args and hasattr(args['fields'], '__iter__'):
                    args['fields'] = {key: value for key, value in args['fields'].items()}
                steps.append({"action": fc.name, **args})
            return steps
        except Exception as e:
            logger.error(f"Error calling Google GenAI API: {e}")
            raise