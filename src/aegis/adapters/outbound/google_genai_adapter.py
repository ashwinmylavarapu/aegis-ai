import json
from typing import Dict, Any, List
from loguru import logger
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold, FunctionDeclaration, Tool
from .base import LLMAdapter

def convert_history_to_gemini(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    gemini_history = []
    for message in history:
        role = message["role"]
        
        if role == "assistant":
            parts = []
            for tool_call in message.get("tool_calls", []):
                func = tool_call.get("function", {})
                gemini_func_call = {
                    "name": func.get("name"),
                    "args": json.loads(func.get("arguments", '{}'))
                }
                parts.append({'function_call': gemini_func_call})
            
            if parts:
                gemini_history.append({'role': 'model', 'parts': parts})

        elif role == "tool":
            gemini_history.append({
                'role': 'function',
                'parts': [{
                    'function_response': {
                        'name': message.get('name'), 
                        'response': {'content': message.get('content')}
                    }
                }]
            })

    return gemini_history


class GoogleGenAIAdapter(LLMAdapter):
    def __init__(self, config: Dict[str, Any]):
        llm_config = config.get("llm", {}).get("google_genai_studio", {})
        api_key, model_name = llm_config.get("api_key"), llm_config.get("model", "gemini-pro")
        if not api_key: raise ValueError("Google GenAI config missing 'api_key' in config.yaml")
        genai.configure(api_key=api_key)
        
        # --- FIX: Update tool definitions and system prompt ---
        tool_declarations = [
            FunctionDeclaration(name="navigate", description="Navigates to a URL.", parameters={"type": "object", "properties": {"url": {"type": "string"}}}),
            FunctionDeclaration(name="search_jobs", description="Performs a job search on a site like LinkedIn.", parameters={"type": "object", "properties": {"query": {"type": "string"}}}),
            FunctionDeclaration(
                name="wait_for_element",
                description="Waits for an element to appear on the page.",
                parameters={"type": "object", "properties": {
                    "selector": {"type": "string"},
                    "timeout": {"type": "integer", "description": "Optional wait time in milliseconds (e.g., 60000 for 60 seconds)."}
                }},
            ),
            FunctionDeclaration(
                name="extract_data",
                description="Extracts data from a list of elements.",
                parameters={"type": "object", "properties": {
                    "selector": {"type": "string", "description": "CSS selector for each item in the list."},
                    "limit": {"type": "integer"},
                    "fields": {"type": "array", "items": {"type": "string"}, "description": "Names of data to extract, e.g., ['title', 'company', 'url']"}
                }},
            ),
            FunctionDeclaration(name="finish_task", description="Call when the goal is fully accomplished.", parameters={"type": "object", "properties": {"summary": {"type": "string"}}}),
        ]
        
        self.system_instruction = (
            "You are an expert AI web automation agent. Your goal is to fulfill the user's request by creating a plan. "
            "Think step-by-step. For long-running actions like starting a machine, use the `wait_for_element` tool with a longer `timeout`, for example, 60000 milliseconds for a 60-second wait. "
            "If a tool call results in an error, analyze the error and change your strategy. If you are stuck, use the `finish_task` tool to report the failure."
        )
        # --- END FIX ---

        self.model = genai.GenerativeModel(model_name, tools=tool_declarations, system_instruction=self.system_instruction)
        logger.info(f"GoogleGenAIAdapter initialized for model: {model_name}")

    async def generate_plan(self, goal: str, history: List[Dict[str, Any]] = []) -> List[Dict[str, Any]]:
        logger.info(f"Generating next step for goal: '{goal.strip()}'")
        full_conversation = [{"role": "user", "parts": [{"text": goal}]}]
        full_conversation.extend(convert_history_to_gemini(history))

        try:
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            response = await self.model.generate_content_async(
                full_conversation,
                safety_settings=safety_settings
            )

            response_part = response.candidates[0].content.parts[0]
            logger.debug(f"Google GenAI response part: {response_part}")

            steps = []
            if hasattr(response_part, 'function_call') and response_part.function_call:
                fc = response_part.function_call
                args = {key: value for key, value in fc.args.items()}
                if 'fields' in args and hasattr(args['fields'], '__iter__'):
                    args['fields'] = list(args['fields'])
                steps.append({"action": fc.name, **args})

            if not steps: logger.warning("LLM did not return any function calls.")
            return steps
        except Exception as e:
            logger.error(f"Error calling Google GenAI API or parsing response: {e}")
            return []